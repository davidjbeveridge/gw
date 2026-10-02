"""Explicit learning plugins, reviewable proposals, bounded worker execution.

Default analysis is deterministic. Research is an explicitly configured external
worker, not an implicit license to browse or spend tokens in an observer.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
import pathlib
import signal
import sqlite3
import subprocess
import tempfile
import time
import uuid
from typing import Protocol

PROTOCOL='gw.learning/1'
DEFAULTS={'mode':'propose','lookback_days':14,'max_proposals':20,'strategies':['thematic'],
          'plugins':{'tool_optimization':{'enabled':True,'threshold':3},'skill_expansion':{'enabled':True,'threshold':3},
                     'research':{'enabled':False,'topics':[],'interval_seconds':86400}},
          'executor':{'argv':[],'timeout_seconds':120,'max_output_bytes':262144,'allowed_kinds':['research_job']},
          'promotion':'review'}


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()


class LearningPlugin(Protocol):
    name:str
    version:str
    def propose(self,context:dict,settings:dict)->list[dict]: ...


class ToolOptimization:
    name='tool_optimization';version='1'
    def propose(self,c,s):
        return [{'key':x['action_hash'],'kind':'tool_plan','title':'Review repeated '+x.get('tool','operation'),
                 'body':'This action succeeded repeatedly. Inspect its source fixtures, identify stable inputs and outputs, and test a deterministic wrapper before registration. Repetition is not proof of equivalent intent or reusable consent.',
                 'evidence':[x['reference']],'goal_ids':['tool_efficiency','repeat_work']} for x in c.get('repetitions',[]) if x.get('successes',0)>=s.get('threshold',3)]


class SkillExpansion:
    name='skill_expansion';version='1'
    def propose(self,c,s):
        return [{'key':x['id'],'kind':'guidance','title':'Review guidance for '+x['id'],
                 'body':'Repeated interventions were observed for the configured goal '+x['id']+'. Review the goal and the cited actions. Decide whether instructions, tools, or the policy need correction. This pattern does not establish that the agent or policy was right.',
                 'evidence':x.get('evidence',[])[:20],'goal_ids':[x['id']]} for x in c.get('goal_patterns',[]) if x.get('interventions',0)>=s.get('threshold',3)]


class Research:
    name='research';version='1'
    def propose(self,c,s):
        if 'expansion' not in c['strategies']:return []
        interval=s.get('interval_seconds',86400)
        if type(interval) is not int or interval<3600:raise ValueError('Research cadence must be at least hourly')
        result=[]
        for topic in s.get('topics',[]):
            if not isinstance(topic,dict) or not topic.get('query') or not topic.get('id'):raise ValueError('Research topics need explicit IDs and queries')
            result.append({'key':str(topic['id'])+':'+str(int(c['as_of']//interval)), 'kind':'research_job',
                           'title':'Research: '+topic['id'],'body':topic['query'],'evidence':[], 'goal_ids':topic.get('goal_ids',[]),
                           'authorization_basis':'explicit_configured_topic','topic_id':topic['id']})
        return result


def validate(c):
    if not isinstance(c,dict) or set(c)-set(DEFAULTS):raise ValueError('Unknown learning setting')
    if c.get('mode') not in {'off','propose','auto'}:raise ValueError('Invalid learning mode')
    if c.get('promotion')!='review':raise ValueError('Live harness promotion requires review in this release')
    if type(c.get('lookback_days')) is not int or not 1<=c['lookback_days']<=365:raise ValueError('Invalid lookback')
    if type(c.get('max_proposals')) is not int or not 1<=c['max_proposals']<=100:raise ValueError('Invalid proposal limit')
    if not isinstance(c.get('strategies'),list) or not set(c['strategies'])<={'thematic','expansion'}:raise ValueError('Unknown learning strategy')
    if not isinstance(c.get('plugins'),dict):raise ValueError('Learning plugins must be an object')
    e=c.get('executor',{})
    if not isinstance(e,dict) or set(e)-{'argv','timeout_seconds','max_output_bytes','allowed_kinds'}:raise ValueError('Invalid executor config')
    if not isinstance(e.get('allowed_kinds'),list) or not set(e['allowed_kinds'])<={'research_job','guidance','tool_plan'}:raise ValueError('Invalid worker kinds')
    if not isinstance(e.get('argv'),list) or any(not isinstance(a,str) or '\0' in a for a in e['argv']):raise ValueError('Executor argv must be literal strings')
    if type(e.get('timeout_seconds')) is not int or not 1<=e['timeout_seconds']<=3600:raise ValueError('Invalid worker time budget')
    if type(e.get('max_output_bytes')) is not int or not 1024<=e['max_output_bytes']<=1048576:raise ValueError('Invalid worker output budget')


class LearningCoordinator:
    def __init__(self,directory,*,observer=None):
        self.directory=pathlib.Path(directory).expanduser().absolute()
        if self.directory.is_symlink():raise ValueError('Unsafe learning directory')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.observer=observer
        path=self.directory/'learning.sqlite3'
        if path.is_symlink():raise ValueError('Unsafe learning database')
        self.db=sqlite3.connect(path,timeout=5);self.db.row_factory=sqlite3.Row
        if os.name!='nt':path.chmod(0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,plugin TEXT,version TEXT,kind TEXT,status TEXT,created REAL,payload TEXT,input_hash TEXT,config_hash TEXT,result TEXT);
CREATE TABLE IF NOT EXISTS journal(id TEXT PRIMARY KEY,proposal TEXT,kind TEXT,at REAL,detail TEXT);
CREATE TABLE IF NOT EXISTS configurations(hash TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS passes(id TEXT PRIMARY KEY,at REAL,input_hash TEXT,config_hash TEXT,result TEXT);''')
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()
    def config(self):
        p=self.directory/'config.json'
        return json.loads(p.read_text()) if p.exists() else json.loads(canonical(DEFAULTS))
    def configure(self,c):
        def merge(base,overlay):
            out=json.loads(canonical(base))
            for k,v in overlay.items():out[k]=merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else v
            return out
        c=merge(DEFAULTS,c)
        validate(c)
        with self.db:self.db.execute("INSERT OR IGNORE INTO configurations VALUES (?,?)",(digest(c),canonical(c)))
        p=self.directory/'config.json';tmp=p.with_suffix('.tmp-'+uuid.uuid4().hex)
        tmp.write_text(canonical(c));tmp.chmod(0o600);os.replace(tmp,p);return c
    def _journal(self,pid,kind,detail):
        key=uuid.uuid4().hex;at=time.time()
        row=self.db.execute('SELECT payload FROM proposals WHERE id=?',(pid,)).fetchone()
        if row:detail={**detail,'goal_ids':json.loads(row[0]).get('goal_ids',[])}
        self.db.execute('INSERT INTO journal VALUES (?,?,?,?,?)',(key,pid,kind,at,canonical(detail)))
        if self.observer:
            # Failure of telemetry never changes the learning state transition.
            try:self.observer('learning.'+kind,{'proposal_id':pid,'journal_id':key,**detail},int(at*1e9),time.time_ns())
            except Exception:pass
    def get(self,pid):
        row=self.db.execute('SELECT * FROM proposals WHERE id=?',(pid,)).fetchone()
        if not row:raise ValueError('Unknown proposal')
        out=dict(row);out['payload']=json.loads(out['payload']);out['result']=json.loads(out['result']) if out['result'] else None
        stored_config=self.db.execute('SELECT body FROM configurations WHERE hash=?',(out['config_hash'],)).fetchone()
        out['configuration']=json.loads(stored_config[0]) if stored_config else None
        out['history']=[{**dict(x),'detail':json.loads(x['detail'])} for x in self.db.execute('SELECT * FROM journal WHERE proposal=? ORDER BY at,id',(pid,))]
        return out
    def list(self,limit=100):return [self.get(r[0]) for r in self.db.execute('SELECT id FROM proposals ORDER BY created DESC LIMIT ?',(max(1,min(int(limit),1000)),)).fetchall()]
    def run(self,context):
        c=self.config();validate(c)
        if c['mode']=='off':return {'status':'disabled','proposals':[],'model_calls':0}
        context={**context,'as_of':context.get('as_of',time.time()),'strategies':c['strategies'],'lookback_days':c['lookback_days']}
        results=[];errors=[];ch=digest(c);ih=digest(context)
        with self.db:self.db.execute('INSERT OR IGNORE INTO configurations VALUES (?,?)',(ch,canonical(c)))
        for name,settings in c['plugins'].items():
            if not settings.get('enabled',True):continue
            if name!='research' and 'thematic' not in c['strategies']:continue
            try:
                if name in {'tool_optimization','skill_expansion','research'}:
                    plugin={'tool_optimization':ToolOptimization,'skill_expansion':SkillExpansion,'research':Research}[name]()
                else:
                    matches=list(importlib.metadata.entry_points(group='gw.learning.plugins',name=name))
                    if len(matches)!=1:raise ValueError('Expected exactly one installed learning plugin')
                    plugin=matches[0].load()()
                for p in plugin.propose(context,settings):
                    if len(results)>=c['max_proposals']:break
                    if not isinstance(p,dict) or p.get('kind') not in {'guidance','tool_plan','research_job'} or not all(isinstance(p.get(k),str) for k in ('key','title','body')):
                        raise ValueError('Invalid plugin proposal')
                    if len(canonical(p))>32768:raise ValueError('Proposal exceeds budget')
                    pid=digest([plugin.name,plugin.version,p['key'],ch,p['body']])
                    with self.db:
                        inserted=self.db.execute('INSERT OR IGNORE INTO proposals VALUES (?,?,?,?,?,?,?,?,?,NULL)',(pid,plugin.name,plugin.version,p['kind'],'proposed',time.time(),canonical(p),ih,ch)).rowcount
                        if inserted:self._journal(pid,'proposed',{'plugin':name,'kind':p['kind'],'input_hash':ih,'config_hash':ch})
                    results.append({'id':pid,'new':bool(inserted),'kind':p['kind']})
                    if c['mode']=='auto' and p['kind'] in c['executor']['allowed_kinds'] and c['executor']['argv']:
                        if self.get(pid)['status']=='proposed':self.review(pid,True,'explicit auto mode and configured worker kinds')
                        if self.get(pid)['status']=='approved':self.execute(pid)
            except Exception as exc:errors.append({'plugin':name,'error':type(exc).__name__})
        result={'status':'partial' if errors else 'complete','proposals':results,'errors':errors,'analysis':'deterministic defaults; custom plugins are trusted code'}
        pass_id=uuid.uuid4().hex;at=time.time()
        with self.db:self.db.execute('INSERT INTO passes VALUES (?,?,?,?,?)',(pass_id,at,ih,ch,canonical(result)))
        if self.observer:
            try:self.observer('learning.pass',{'pass_id':pass_id,'status':result['status'],'proposals':len(results),'new_proposals':sum(bool(x['new']) for x in results),'errors':errors,'input_hash':ih,'config_hash':ch,'lookback_days':c['lookback_days'],'strategies':c['strategies']},int(at*1e9),time.time_ns())
            except Exception:pass
        return result
    def review(self,pid,approve,reason='operator review'):
        p=self.get(pid)
        if p['status']!='proposed':raise ValueError('Only proposed items can be reviewed')
        with self.db:
            changed=self.db.execute('UPDATE proposals SET status=? WHERE id=? AND status=?',('approved' if approve else 'rejected',pid,'proposed')).rowcount
            if not changed:raise ValueError('Proposal changed during review')
            self._journal(pid,'approved' if approve else 'rejected',{'reason':reason[:1000],'by':'operator_or_explicit_auto_policy'})
        return self.get(pid)
    def execute(self,pid):
        p=self.get(pid);c=self.config();validate(c)
        if p['kind'] not in c['executor']['allowed_kinds']:raise ValueError('Worker kind is not explicitly enabled')
        if not c['executor']['argv']:raise ValueError('No worker configured; no process launched')
        if p['config_hash']!=digest(c):raise ValueError('Configuration changed since proposal; regenerate and review')
        with self.db:
            if not self.db.execute("UPDATE proposals SET status='running' WHERE id=? AND status='approved'",(pid,)).rowcount:
                raise ValueError('Job is not approved or was claimed by another worker')
            self._journal(pid,'started',{'executor_hash':digest(c['executor']['argv'])})
        start=time.monotonic();result={'status':'failed'}
        try:
            request={'protocol':PROTOCOL,'job_id':pid,'kind':p['kind'],'topic':p['payload']['body'],'proposal':p['payload'],'goal_ids':p['payload'].get('goal_ids',[]),
                     'limits':c['executor'],'instructions':'Return JSON with report (Markdown), optional sources and usage. Do not change harness policy or files.'}
            with tempfile.TemporaryDirectory(prefix='gw-research-') as tmp:
                # No shell interpolation and no output-controlled execution. The
                # configured worker has the user's OS rights, not a sandbox.
                with tempfile.TemporaryFile() as output:
                    proc=subprocess.Popen(c['executor']['argv'],stdin=subprocess.PIPE,stdout=output,stderr=subprocess.DEVNULL,
                                          cwd=tmp,start_new_session=(os.name!='nt'))
                    data=canonical(request).encode();deadline=time.monotonic()+c['executor']['timeout_seconds']
                    try:
                        while True:
                            if time.monotonic()>deadline or os.fstat(output.fileno()).st_size>c['executor']['max_output_bytes']:
                                raise TimeoutError('Worker exceeded its time or output budget')
                            try:proc.communicate(data,timeout=.1);break
                            except subprocess.TimeoutExpired:data=None
                        output.seek(0);out=output.read(c['executor']['max_output_bytes']+1)
                    except BaseException:
                        if os.name!='nt':
                            try:os.killpg(proc.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                        else:proc.kill()
                        proc.communicate();raise
                if proc.returncode!=0 or len(out)>c['executor']['max_output_bytes']:raise ValueError('Worker failed or exceeded output budget')
                response=json.loads(out)
                if not isinstance(response,dict) or not isinstance(response.get('report'),str) or not response['report'].strip():raise ValueError('Worker must return a report')
                result={'status':'succeeded','report':response['report'],'sources':response.get('sources',[]),'usage':response.get('usage'),
                        'cost_basis':'worker_reported_not_verified','harness_changes':[]}
        except Exception as exc:result={'status':'failed','error':type(exc).__name__,'harness_changes':[]}
        result['elapsed_seconds']=time.monotonic()-start
        with self.db:
            self.db.execute('UPDATE proposals SET status=?,result=? WHERE id=?',(result['status'],canonical(result),pid))
            self._journal(pid,result['status'],{'elapsed_seconds':result['elapsed_seconds'],'error':result.get('error'),'harness_changes':[]})
        return self.get(pid)
    def promote(self,pid,destination):
        """Publish a reviewed immutable artifact; do not edit a live agent policy."""
        p=self.get(pid)
        if p['status'] not in {'approved','succeeded'}:raise ValueError('Review or successful worker output required')
        if p['kind']=='research_job' and p['status']!='succeeded':raise ValueError('Research must complete before publication')
        root=pathlib.Path(destination).expanduser().absolute()
        if root.is_symlink():raise ValueError('Unsafe artifact destination')
        root=root.resolve()
        root.mkdir(parents=True,exist_ok=True)
        content='# '+p['payload']['title']+'\n\n'+((p.get('result') or {}).get('report') or p['payload']['body'])+'\n\nSource proposal: '+pid+'\n'
        path=root/(pid+'.md')
        with path.open('x',encoding='utf-8') as f:f.write(content)
        with self.db:
            self.db.execute("UPDATE proposals SET status='published' WHERE id=?",(pid,))
            self._journal(pid,'published',{'path':str(path),'hash':digest(content),'activation':'not_installed_into_a_live_harness'})
        return {'artifact':str(path),'hash':digest(content),'live_harness_changed':False}
