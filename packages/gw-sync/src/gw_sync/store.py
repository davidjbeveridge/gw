"""Immutable harness bundles with content-addressed local storage and CAS channels.

Explicit file sets only. Pulls are reviewed plans, never background writes to a
running agent's policy or a vehicle for synchronizing credentials/transcripts.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import tempfile
import time
import uuid
from typing import Protocol

PROTOCOL='gw.bundle/1'
MAX_FILE=8*1024*1024
MAX_TOTAL=128*1024*1024


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def sha(data):return hashlib.sha256(data).hexdigest()
def hash_json(v):return sha(canonical(v).encode())


class BundleProvider(Protocol):
    def put_blob(self,data:bytes)->str: ...
    def get_blob(self,content_hash:str)->bytes: ...
    def publish(self,manifest:dict,*,channel:str,expected:str|None)->dict: ...
    def resolve(self,reference:str)->dict: ...


def safe_path(value):
    if not isinstance(value,str) or not value or '\\' in value or '\0' in value or ':' in value:
        raise ValueError('Invalid portable bundle path')
    p=pathlib.PurePosixPath(value)
    if p.is_absolute() or any(part in {'.','..'} for part in value.split('/')):
        raise ValueError('Bundle path escapes its root')
    reserved={'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
    if any(part.endswith((' ','.')) or part.split('.')[0].upper() in reserved for part in p.parts):raise ValueError('Nonportable Windows path')
    return p


def target(root,relative):
    path=root.joinpath(*safe_path(relative).parts)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Symlink paths are not synchronized')
    if not path.is_relative_to(root):raise ValueError('Path outside destination')
    return path


def scan(relative,data):
    """Conservative exclusions plus best-effort literal-secret checks, not DLP."""
    parts=pathlib.PurePosixPath(relative).parts
    for name in parts:
        low=name.lower()
        if low in {'.git','node_modules','__pycache__','auth.json','credentials.json','.credentials.json','api-token','.gw-sync-apply.lock'} or low.startswith('.env') or low.endswith(('.sqlite','.sqlite3','.db','.jsonl','.pem','.key')):
            raise ValueError('Credentials, logs, databases and generated dependencies are excluded')
    decoded=data.decode('utf-8')
    if re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|rk)-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}',decoded):
        raise ValueError('Potential secret detected in bundle')
    # References and variable names are portable; literal credentials are not.
    for match in re.finditer(r'(?i)["\'](?:password|secret|api[_-]?key|access_token|refresh_token|authorization)["\']\s*:\s*["\']([^"\']+)',decoded):
        v=match.group(1)
        if not v.startswith(('$','os.environ/','credential://','[REDACTED]','YOUR_')):
            raise ValueError('Literal credential field detected')


def write_atomic(path,data,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.gw-sync-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


class LocalBundleStore:
    def __init__(self,directory,*,observer=None):
        self.observer=observer
        self.directory=pathlib.Path(directory).expanduser().absolute()
        if self.directory.is_symlink():raise ValueError('Unsafe bundle store')
        self.directory=self.directory.resolve()
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(self.directory/'channels.sqlite3',timeout=5)
        self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL')
        if os.name!='nt':(self.directory/'channels.sqlite3').chmod(0o600)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS channels(name TEXT PRIMARY KEY,reference TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS applications(root TEXT PRIMARY KEY,reference TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal(id TEXT PRIMARY KEY,kind TEXT,at REAL,details TEXT);''')
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()
    def _journal(self,kind,details):
        key=uuid.uuid4().hex;at=time.time()
        self.db.execute('INSERT INTO journal VALUES (?,?,?,?)',(key,kind,at,canonical(details)))
        if self.observer:
            try:self.observer('sync.'+kind,{'journal_id':key,'reference':details.get('reference'),'files_changed':len(details.get('changed',[]))},int(at*1e9),time.time_ns())
            except Exception:pass
    def put_blob(self,data):
        if not isinstance(data,bytes) or len(data)>MAX_FILE:raise ValueError('Invalid blob')
        h=sha(data);p=self.directory/'blobs'/h[:2]/h
        if p.exists():
            if sha(p.read_bytes())!=h:raise ValueError('Stored blob is corrupt')
        else:write_atomic(p,data)
        return h
    def get_blob(self,h):
        if not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h):raise ValueError('Invalid content hash')
        p=self.directory/'blobs'/h[:2]/h
        if p.is_symlink() or p.stat().st_size>MAX_FILE:raise ValueError('Unsafe blob')
        data=p.read_bytes()
        if sha(data)!=h:raise ValueError('Blob hash verification failed')
        return data
    def validate(self,m):
        if not isinstance(m,dict) or set(m)!={'protocol','files'} or m['protocol']!=PROTOCOL or not isinstance(m['files'],list) or len(m['files'])>5000:
            raise ValueError('Invalid bundle manifest')
        total=0;paths=set()
        for item in m['files']:
            if set(item)!={'path','hash','size','executable'}:raise ValueError('Invalid file descriptor')
            safe_path(item['path'])
            collision=item['path'].casefold()
            if collision in paths:raise ValueError('Duplicate or case-colliding path')
            paths.add(collision)
            if type(item['size']) is not int or not 0<=item['size']<=MAX_FILE or type(item['executable']) is not bool:raise ValueError('Invalid blob metadata')
            if not isinstance(item['hash'],str) or not re.fullmatch('[a-f0-9]{64}',item['hash']):raise ValueError('Invalid hash')
            total+=item['size']
        if total>MAX_TOTAL:raise ValueError('Bundle exceeds byte limit')
        # Do not allow a file to be another file's parent.
        for path in paths:
            if any(str(p).casefold() in paths for p in pathlib.PurePosixPath(path).parents if str(p)!='.'):
                raise ValueError('File/directory path collision')
    def publish(self,manifest,*,channel,expected=None):
        self.validate(manifest)
        if not re.fullmatch('[A-Za-z0-9._-]{1,100}',channel):raise ValueError('Invalid channel')
        for f in manifest['files']:
            data=self.get_blob(f['hash'])
            if len(data)!=f['size']:raise ValueError('Blob size mismatch')
            scan(f['path'],data)
        ref=hash_json(manifest);path=self.directory/'manifests'/(ref+'.json')
        if not path.exists():write_atomic(path,canonical(manifest).encode())
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            current=self.db.execute('SELECT reference FROM channels WHERE name=?',(channel,)).fetchone()
            actual=current[0] if current else None
            if actual!=expected and actual!=ref:raise ValueError('Channel changed; review its current reference')
            self.db.execute('INSERT OR REPLACE INTO channels VALUES (?,?,?)',(channel,ref,time.time()))
            self._journal('published',{'channel':channel,'reference':ref,'previous':actual})
        return {'reference':ref,'channel':channel,'previous':actual,'files':len(manifest['files'])}
    def resolve(self,ref):
        row=self.db.execute('SELECT reference FROM channels WHERE name=?',(ref,)).fetchone()
        ref=row[0] if row else ref
        if not isinstance(ref,str) or not re.fullmatch('[a-f0-9]{64}',ref):raise ValueError('Unknown bundle/channel')
        p=self.directory/'manifests'/(ref+'.json')
        if p.is_symlink() or p.stat().st_size>4*1024*1024:raise ValueError('Unsafe manifest')
        m=json.loads(p.read_text());self.validate(m)
        if hash_json(m)!=ref:raise ValueError('Manifest hash verification failed')
        return {'reference':ref,'manifest':m}
    def history(self):return [{**dict(r),'details':json.loads(r['details'])} for r in self.db.execute('SELECT * FROM journal ORDER BY at DESC LIMIT 200')]


def pack(store,root,includes,*,channel,expected=None):
    root=pathlib.Path(root).expanduser().resolve();names=set()
    if not root.is_dir() or not includes:raise ValueError('Explicit existing root and include patterns required')
    for pattern in includes:
        safe_path(pattern)
        for p in root.glob(pattern):
            if p.is_symlink():raise ValueError('Symlinks are excluded')
            if p.is_file():names.add(p.relative_to(root).as_posix())
    if not names:raise ValueError('Include patterns matched no files')
    files=[];total=0
    for relative in sorted(names):
        p=target(root,relative);size=p.stat().st_size
        if size>MAX_FILE or total+size>MAX_TOTAL:raise ValueError('Bundle size budget exceeded')
        data=p.read_bytes();scan(relative,data);total+=len(data)
        files.append({'path':relative,'hash':store.put_blob(data),'size':len(data),'executable':bool(p.stat().st_mode&0o111)})
    return store.publish({'protocol':PROTOCOL,'files':files},channel=channel,expected=expected)


def plan(store,reference,destination):
    root=pathlib.Path(destination).expanduser().absolute()
    if root.is_symlink():raise ValueError('Unsafe destination')
    root=root.resolve()
    bundle=store.resolve(reference)
    prior=store.db.execute('SELECT reference FROM applications WHERE root=?',(str(root),)).fetchone()
    previous=store.resolve(prior[0])['manifest'] if prior else {'files':[]}
    old={f['path']:f['hash'] for f in previous['files']};changes=[]
    for f in bundle['manifest']['files']:
        p=target(root,f['path']);data=store.get_blob(f['hash']);scan(f['path'],data)
        if p.exists() and (not p.is_file() or p.stat().st_size>MAX_FILE):raise ValueError('Destination path is not an admissible file')
        actual=sha(p.read_bytes()) if p.exists() else None
        state='unchanged' if actual==f['hash'] else 'create' if actual is None else 'update' if actual==old.get(f['path']) else 'conflict'
        changes.append({**f,'status':state,'expected_local':actual})
    obsolete=sorted(set(old)-{f['path'] for f in bundle['manifest']['files']})
    result={'protocol':PROTOCOL,'reference':bundle['reference'],'destination':str(root),'previous_reference':prior[0] if prior else None,
            'changes':changes,'obsolete_not_deleted':obsolete,'conflicts':sum(f['status']=='conflict' for f in changes)}
    result['plan_hash']=hash_json(result)
    return result


@contextlib.contextmanager
def destination_lock(root):
    # Cooperative apply lock only. Does not protect against another same-user
    # process that deliberately ignores the lock. Crash leftovers require review.
    root=pathlib.Path(root)
    if root.is_symlink():raise ValueError('Unsafe destination')
    root.mkdir(parents=True,exist_ok=True)
    path=root/'.gw-sync-apply.lock'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        os.write(fd,str(os.getpid()).encode());yield
    finally:os.close(fd);path.unlink()


def apply(store,reviewed):
    if not isinstance(reviewed,dict) or 'destination' not in reviewed:raise ValueError('Reviewed plan required')
    # Validate plan and destination before creating even a lock file.
    if reviewed.get('plan_hash')!=hash_json({k:v for k,v in reviewed.items() if k!='plan_hash'}):raise ValueError('Plan was modified')
    root=pathlib.Path(reviewed['destination']).expanduser().absolute()
    if any(p.is_symlink() for p in (root,*root.parents)):raise ValueError('Unsafe destination')
    with destination_lock(root):return _apply_locked(store,reviewed)


def _apply_locked(store,reviewed):
    expected=reviewed.get('plan_hash');body={k:v for k,v in reviewed.items() if k!='plan_hash'}
    if expected!=hash_json(body):raise ValueError('Plan was modified')
    current=plan(store,reviewed['reference'],reviewed['destination'])
    if current['plan_hash']!=expected:raise ValueError('Destination changed after plan review; regenerate the plan')
    if current['conflicts']:raise ValueError('Conflicts require manual reconciliation')
    root=pathlib.Path(current['destination']);root.mkdir(parents=True,exist_ok=True)
    # Validate everything before the first mutation, then recheck each file.
    backups=[]
    try:
        for item in current['changes']:
            if item['status']=='unchanged':continue
            p=target(root,item['path']);old=p.read_bytes() if p.exists() else None
            if (sha(old) if old is not None else None)!=item['expected_local']:raise ValueError('Concurrent local edit; refusing to overwrite')
            old_mode=p.stat().st_mode&0o777 if p.exists() else None
            data=store.get_blob(item['hash'])
            backups.append((p,old,old_mode,item['hash']))
            write_atomic(p,data,0o755 if item['executable'] else 0o644)
        with store.db:
            store.db.execute('INSERT OR REPLACE INTO applications VALUES (?,?)',(str(root),current['reference']))
            store._journal('applied',{'reference':current['reference'],'destination':str(root),'plan_hash':expected,
                                     'changed':[f['path'] for f in current['changes'] if f['status']!='unchanged']})
    except Exception:
        # Do not erase another writer's subsequent edit while rolling back.
        for p,data,mode,new_hash in reversed(backups):
            if p.exists() and sha(p.read_bytes())==new_hash:
                if data is None:p.unlink()
                else:write_atomic(p,data,mode)
        raise
    return {'applied':True,'reference':current['reference'],'files_changed':len(backups),'obsolete_not_deleted':current['obsolete_not_deleted'],
            'agent_activation':'not_performed; review/trust/restart through the native harness'}


class SyncWorkspace:
    """Local application state around any BundleProvider, including a remote one.

    Provider implementations never need SQLite or knowledge of client paths.
    """
    def __init__(self,provider,directory,*,observer=None):
        self.provider=provider
        self.state=LocalBundleStore(directory,observer=observer)
        self.db=self.state.db
    def _journal(self,kind,details):self.state._journal(kind,details)
    def put_blob(self,data):return self.provider.put_blob(data)
    def get_blob(self,content_hash):
        data=self.provider.get_blob(content_hash)
        if not isinstance(data,bytes) or len(data)>MAX_FILE or sha(data)!=content_hash:raise ValueError('Provider returned an invalid blob')
        return data
    def publish(self,manifest,*,channel,expected=None):
        result=self.provider.publish(manifest,channel=channel,expected=expected)
        with self.db:self._journal('published',{'channel':channel,**result})
        return result
    def resolve(self,reference):
        bundle=self.provider.resolve(reference)
        if not isinstance(bundle,dict) or set(bundle)!={'reference','manifest'}:raise ValueError('Invalid provider manifest envelope')
        self.state.validate(bundle['manifest'])
        if hash_json(bundle['manifest'])!=bundle['reference']:raise ValueError('Provider manifest hash mismatch')
        return bundle
    def history(self):return self.state.history()
    def close(self):
        self.state.close()
        if hasattr(self.provider,'close'):self.provider.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()


def open_provider(name,options):
    if name=='local':return LocalBundleStore(options['directory'])
    if name=='http':
        from .http import HttpBundleProvider
        return HttpBundleProvider(**options)
    import importlib.metadata
    matches=list(importlib.metadata.entry_points(group='gw.sync.providers',name=name))
    if len(matches)!=1:raise ValueError('Expected one installed BundleProvider')
    provider=matches[0].load()(options)
    for method in ('put_blob','get_blob','publish','resolve'):
        if not callable(getattr(provider,method,None)):raise ValueError('Incompatible bundle provider')
    return provider
