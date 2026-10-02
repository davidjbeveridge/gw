"""Local trace index. Canonical GW verdicts remain in GW's event ledger.

Only run manifests, source locators and compact measurements live here. Imported
transcripts are indexed by byte range and hash, not copied into another archive.
"""
from __future__ import annotations
import json
import os
import pathlib
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from .contract import PROTOCOL, METRICS, canonical, connect, digest, private_dir, redact, text, validate_observation

SCHEMA = '''
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,name TEXT NOT NULL,project TEXT NOT NULL,
 started_ns INTEGER NOT NULL,finished_ns INTEGER,manifest TEXT NOT NULL,outcome TEXT NOT NULL DEFAULT 'unknown',evidence TEXT);
CREATE TABLE IF NOT EXISTS bindings(project TEXT,client TEXT,run_id TEXT NOT NULL,PRIMARY KEY(project,client));
CREATE TABLE IF NOT EXISTS members(session_id TEXT PRIMARY KEY,run_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,session_id TEXT,parent_id TEXT,
 kind TEXT NOT NULL,start_ns INTEGER NOT NULL,end_ns INTEGER NOT NULL,attributes TEXT NOT NULL,source TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS obs_run_time ON observations(run_id,start_ns,id);
CREATE INDEX IF NOT EXISTS obs_session ON observations(session_id,kind);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,kind TEXT NOT NULL,path TEXT NOT NULL,metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(hash TEXT PRIMARY KEY,kind TEXT NOT NULL,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS run_overhead(run_id TEXT PRIMARY KEY,total_ns INTEGER NOT NULL,samples INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS diagnostics(kind TEXT PRIMARY KEY,count INTEGER NOT NULL,last_ns INTEGER NOT NULL);
'''


def git_snapshot(project):
    """Read-only fingerprint; never resets code or stores the patch."""
    def run(*args):
        try:
            r=subprocess.run(['git','-C',project,*args],capture_output=True,timeout=5)
            return r.stdout if r.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired): return None
    head=run('rev-parse','HEAD'); status=run('status','--porcelain=v1','-z'); diff=run('diff','--binary','HEAD')
    return {'commit':head.decode().strip() if head else None,
            'dirty':bool(status) if status is not None else None,
            'tracked_diff_hash':digest(diff.hex()) if diff is not None else None,
            'status_hash':digest(status.hex()) if status is not None else None,
            'untracked_contents_captured':False,
            'coverage':'tracked_changes_only' if head else 'git_unavailable'}


class LocalTraceRepository:
    def __init__(self,directory,*,core_database=None):
        self.directory=private_dir(directory)
        self.db=connect(self.directory/'traces.sqlite3')
        self.db.executescript(SCHEMA)
        self._core={}
        if core_database: self.register_source(core_database,'gw.sqlite',source_id='gw-core')

    def close(self):
        for db in self._core.values(): db.close()
        self.db.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

    def snapshot(self,kind,value):
        body=canonical(redact(value)); key=digest([kind,body])
        with self.db: self.db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?)',(key,kind,body))
        return key

    def register_source(self,path,kind,*,source_id=None,metadata=None):
        p=pathlib.Path(path).expanduser().absolute()
        key=source_id or digest([kind,str(p)])
        with self.db:
            old=self.db.execute('SELECT path,kind FROM sources WHERE id=?',(key,)).fetchone()
            if old and (old['path']!=str(p) or old['kind']!=kind): raise ValueError('Source identity conflict')
            self.db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?)',(key,kind,str(p),canonical(metadata or {})))
        return key

    def start(self,name,project,*,harness='unknown',harness_version=None,model=None,prompt_file=None,
              config=None,mode='unknown',bind=False,client=None,run_id=None,capture_prompt=False,metadata=None):
        text(name,'run name'); project=str(pathlib.Path(project).expanduser().resolve())
        key=run_id or uuid.uuid4().hex
        manifest={'protocol':'gw.run/1','harness':harness,'harness_version':harness_version,'model':model,
                  'mode':mode,'workspace':git_snapshot(project),'environment':{'os':platform.system(),
                  'architecture':platform.machine(),'python':platform.python_version()},
                  'config_snapshot':self.snapshot('config',config) if config is not None else None,
                  'metadata':redact(metadata or {}),'prompt':{'hash':None,'source':None},
                  'capture':{'prompt_text':capture_prompt,'transcripts':'references'},
                  'limitations':['No automatic task-quality judgment','No code reset or benchmark orchestration']}
        if prompt_file:
            p=pathlib.Path(prompt_file).expanduser().resolve()
            if p.stat().st_size>1_000_000: raise ValueError('Prompt file exceeds 1 MB')
            data=p.read_bytes()
            manifest['prompt']={'hash':digest(data.hex()),'source':self.register_source(p,'prompt'), 'bytes':len(data)}
            if capture_prompt: manifest['prompt']['snapshot']=self.snapshot('prompt',redact(data.decode()))
        now=time.time_ns()
        with self.db:
            if bind:
                old=self.db.execute('SELECT run_id FROM bindings WHERE project=? AND client=?',(project,client or '*')).fetchone()
                if old: raise ValueError('An active run is already bound; finish it or use an explicit run ID')
            self.db.execute('INSERT INTO runs(id,name,project,started_ns,manifest) VALUES (?,?,?,?,?)',(key,name,project,now,canonical(manifest)))
            if bind:self.db.execute('INSERT INTO bindings VALUES (?,?,?)',(project,client or '*',key))
        return self.run(key)

    def run(self,key):
        row=self.db.execute('SELECT * FROM runs WHERE id=?',(key,)).fetchone()
        if not row: raise ValueError('Unknown run')
        out=dict(row);out['manifest']=json.loads(out['manifest']);out['evidence']=json.loads(out['evidence']) if out['evidence'] else None
        return out

    def runs(self,limit=100):
        limit=max(1,min(int(limit),1000))
        return [self.run(r[0]) for r in self.db.execute('SELECT id FROM runs ORDER BY started_ns DESC LIMIT ?',(limit,)).fetchall()]

    def finish(self,key,outcome='unknown',evidence=None):
        if outcome not in {'succeeded','failed','partial','cancelled','unknown'}:raise ValueError('Invalid outcome')
        run=self.run(key)
        if run['finished_ns'] is not None:raise ValueError('Run is already finished')
        end={'source':redact(evidence),'workspace':git_snapshot(run['project']),'asserted_by':'operator'}
        with self.db:
            updated=self.db.execute('UPDATE runs SET finished_ns=?,outcome=?,evidence=? WHERE id=? AND finished_ns IS NULL',(time.time_ns(),outcome,canonical(end),key)).rowcount
            if not updated:raise ValueError('Run was already finished by another process')
            self.db.execute('DELETE FROM bindings WHERE run_id=?',(key,))
        return self.run(key)

    def bind_session(self,session_id,project,client,*,run_id=None,config=None):
        old=self.db.execute('SELECT run_id FROM members WHERE session_id=?',(session_id,)).fetchone()
        if old:
            if run_id and old[0]!=run_id:raise ValueError('Session already belongs to a different run')
            return old[0]
        if not run_id:
            row=self.db.execute("SELECT run_id FROM bindings WHERE project=? AND client IN (?, '*') ORDER BY CASE WHEN client=? THEN 0 ELSE 1 END LIMIT 1",(project,client,client)).fetchone()
            run_id=row[0] if row else None
        if run_id:
            run=self.run(run_id)
            if run['project']!=project or run['finished_ns'] is not None:raise ValueError('Run is finished or belongs to a different project')
        else:
            run_id='session-'+session_id
            if not self.db.execute('SELECT 1 FROM runs WHERE id=?',(run_id,)).fetchone():
                try:self.start('Session '+session_id[:12],project,harness=client,config=config,
                               mode=(config or {}).get('mode','unknown'),run_id=run_id,
                               metadata={'automatic':True,'snapshot_coverage':'partial; supply explicit run metadata for comparisons'})
                except sqlite3.IntegrityError:pass
        with self.db:self.db.execute('INSERT OR IGNORE INTO members VALUES (?,?)',(session_id,run_id))
        return self.db.execute('SELECT run_id FROM members WHERE session_id=?',(session_id,)).fetchone()[0]

    def record_overhead(self,run_id,nanoseconds):
        with self.db:self.db.execute('INSERT INTO run_overhead VALUES (?,?,1) ON CONFLICT(run_id) DO UPDATE SET total_ns=total_ns+excluded.total_ns,samples=samples+1',(run_id,nanoseconds))

    def record(self,event):
        validate_observation(event)
        self.run(event['run_id'])
        with self.db:
            old=self.db.execute('SELECT run_id FROM observations WHERE id=?',(event['id'],)).fetchone()
            if old and old[0]!=event['run_id']:raise ValueError('Observation belongs to another run')
            return bool(self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?)',(
                event['id'],event['run_id'],event.get('session_id'),event.get('parent_id'),event['kind'],event['start_ns'],event['end_ns'],
                canonical(redact(event.get('attributes',{}))),canonical(event.get('source',{})))).rowcount)

    def source(self,reference):
        """Resolve registered locators only. No user-supplied path in dashboard requests."""
        sid=reference.get('source_id'); row=self.db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
        if not row:return {'status':'unregistered'}
        p=pathlib.Path(row['path'])
        if not p.is_file() or p.is_symlink():return {'status':'missing_or_unsafe','reference':reference}
        try:
            if row['kind']=='gw.learning':
                db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=2)
                try:
                    result=db.execute('SELECT payload,result,status FROM proposals WHERE id=?',(reference['proposal_id'],)).fetchone()
                    return {'status':'available','data':{'proposal':json.loads(result[0]),'result':json.loads(result[1]) if result[1] else None,'status':result[2]}} if result else {'status':'missing_proposal'}
                finally:db.close()
            if row['kind']=='gw.sync':
                db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=2)
                try:
                    result=db.execute('SELECT kind,details FROM journal WHERE id=?',(reference['journal_id'],)).fetchone()
                    return {'status':'available','data':{'kind':result[0],'details':json.loads(result[1])}} if result else {'status':'missing_journal'}
                finally:db.close()
            if row['kind']=='gw.sqlite':
                if sid not in self._core:
                    self._core[sid]=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=2)
                result=self._core[sid].execute('SELECT result FROM events WHERE session=? AND event_id=? AND kind=?',
                     (reference['session'],reference['event'],reference['kind'])).fetchone()
                return {'status':'available','data':json.loads(result[0])} if result else {'status':'missing_event'}
            if 'offset' not in reference:return {'status':'reference_only','kind':row['kind'],'name':p.name}
            offset=reference['offset'];length=reference['length']
            if type(offset) is not int or offset<0 or type(length) is not int or not 0<length<=1_048_576:raise ValueError('Invalid source range')
            with p.open('rb') as f:f.seek(offset);data=f.read(length)
            if digest(data.hex())!=reference.get('hash'):return {'status':'changed','reference':reference}
            obj=json.loads(data.decode())
            return {'status':'available','data':redact(obj),'reference':reference}
        except (OSError,ValueError,KeyError,sqlite3.Error):return {'status':'unavailable','reference':reference}

    def event(self,key,*,resolve_source=True):
        row=self.db.execute('SELECT * FROM observations WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Unknown observation')
        result=dict(row);result['attributes']=json.loads(result['attributes']);result['source']=json.loads(result['source'])
        if resolve_source and result['source']:
            result['detail']=self.source(result['source'])
            if result['source'].get('source_id')=='gw-core':
                eid=result['source'].get('event')
                matches=self.db.execute("SELECT id,attributes FROM observations WHERE session_id=? AND kind='agent.tool'",(result['session_id'],))
                result['linked_sources']=[r['id'] for r in matches if json.loads(r['attributes']).get('tool_call_id')==eid][:10]
        return result

    def timeline(self,run_id,*,offset=0,limit=200):
        self.run(run_id);limit=max(1,min(int(limit),500));offset=max(0,int(offset))
        rows=self.db.execute('SELECT id FROM observations WHERE run_id=? ORDER BY start_ns,id LIMIT ? OFFSET ?',(run_id,limit,offset)).fetchall()
        count=self.db.execute('SELECT COUNT(*) FROM observations WHERE run_id=?',(run_id,)).fetchone()[0]
        return {'events':[self.event(r[0],resolve_source=False) for r in rows],'count':count,'offset':offset,'next_offset':offset+limit if offset+limit<count else None}

    def report(self,run_id):
        run=self.run(run_id); kinds=Counter();tools=Counter();goals=defaultdict(Counter);states=Counter();models=Counter();learn=Counter()
        drift=[];usage_lanes=defaultdict(lambda:defaultdict(list));overhead=0.0;cache=Counter();missing_sources=0;turn_ids=set();user_ids=set();edges=[]
        rows=self.db.execute('SELECT * FROM observations WHERE run_id=? ORDER BY start_ns,id',(run_id,))
        first=None;last=None;intercepts=0;effects=Counter();coverage=Counter();parents=set()
        goal_outcomes=[]
        tool_outcomes=Counter();tool_results={};tool_denials=set();tool_executions=set();agent_ids=set()
        tool_entities={};policy_hashes=set();supervisor_usage={k:None for k in METRICS};classifier_calls=0;tool_lanes=defaultdict(lambda:defaultdict(Counter));turn_lanes=defaultdict(lambda:defaultdict(set));user_lanes=defaultdict(lambda:defaultdict(set));task_types=Counter();skill_ids=set()
        for row in rows:
            attrs=json.loads(row['attributes']);source=json.loads(row['source']);kind=row['kind'];kinds[kind]+=1
            first=row['start_ns'] if first is None else min(first,row['start_ns']);last=max(last or 0,row['end_ns'])
            if row['parent_id']:edges.append({'from':row['parent_id'],'to':row['id'],'relation':'parent'})
            if 'tool_class' in attrs:
                entity=(row['session_id'],attrs.get('tool_call_id') or row['id'])
                if entity not in tool_entities or kind=='gw.intercept':tool_entities[entity]=attrs['tool_class']
            if attrs.get('agent_id'):agent_ids.add(attrs['agent_id'])
            entity=(row['session_id'],attrs.get('tool_call_id') or row['id'])
            if attrs.get('event_type')=='tool.before' and attrs.get('decision')=='deny':tool_denials.add(entity)
            if attrs.get('event_type')=='tool.after' or kind=='agent.tool_result':
                tool_executions.add(entity)
                if entity not in tool_results or kind=='gw.intercept':tool_results[entity]=attrs.get('success')
            if attrs.get('task_type'):task_types[attrs['task_type']]+=1
            if attrs.get('skill_id'):skill_ids.add(attrs['skill_id'])
            if attrs.get('model'):models[attrs['model']]+=1
            if kind=='gw.intercept':
                intercepts+=1; effects[attrs.get('decision','unknown')]+=1
                resolved=self.source(source)
                if resolved['status']!='available':
                    missing_sources+=1
                    policy_hashes.add(attrs.get('policy_hash'))
                    for g in attrs.get('goal_index',[]):
                        goals[g['id']][g.get('status','unknown')]+=1
                        if g.get('effect') in {'advise','approve','deny'}:goals[g['id']][g['effect']]+=1
                    coverage['compact_metadata_only']+=1
                else:
                    detail=resolved['data'];audit=detail.get('audit',{})
                    policy_hashes.add(detail.get('policy_hash'))
                    for call in audit.get('classifier_calls',[]):
                        classifier_calls+=1
                        from .contract import normalize_usage
                        u=normalize_usage(call.get('usage',{}))
                        for k,v in u.items():supervisor_usage[k]=(supervisor_usage[k] or 0)+v
                    for g in audit.get('goals',[]):
                        goals[g['id']][g.get('status','unknown')]+=1
                        if g.get('effect') in {'advise','approve','deny'}:goals[g['id']][g['effect']]+=1
                    val=audit.get('alignment_observation')
                    if val is not None:drift.append({'event_id':row['id'],'at_ns':row['start_ns'],'score':val,'prior_ewma':detail.get('metrics',{}).get('drift'),'decision':detail['decision']})
                    overhead+=audit.get('evaluation_ms',0)
                    if audit.get('event_type')=='session.start':user_lanes[row['session_id']]['core'].add(audit.get('event_id'))
                    if audit.get('event_type')=='model.request':turn_lanes[row['session_id']]['proxy'].add(audit.get('event_id'))
                    coverage[audit.get('mode','unknown')]+=1
            elif kind=='knowledge.context':
                cache['error' if attrs.get('status')=='error' else 'hit' if attrs.get('cache_hit') else 'miss']+=1
                for doc in attrs.get('documents',[]):
                    edges.append({'from':'knowledge:'+doc['id']+':'+doc['revision'],'to':row['id'],'relation':'source_passage'})
            if kind=='goal.outcome':goal_outcomes.append({'event_id':row['id'],**attrs})
            if kind.startswith('learning.'):learn[kind]+=1
            if kind in {'model.usage','model.response'} and attrs.get('usage'):
                usage_lanes[row['session_id'] or run_id][attrs.get('usage_source','unknown')].append(attrs)
            if kind=='agent.turn':turn_lanes[row['session_id']][attrs.get('source_lane','import')].add(attrs.get('turn_id',row['id']))
            if kind=='agent.user_turn':user_lanes[row['session_id']][attrs.get('source_lane','import')].add(attrs.get('turn_id',row['id']))
            if attrs.get('source_ref') and isinstance(attrs['source_ref'],str):edges.append({'from':attrs['source_ref'],'to':row['id'],'relation':'evidence'})
        tool_outcomes.update("succeeded" if v is True else "failed" if v is False else "unknown" for v in tool_results.values())
        tools.update(tool_entities.values())
        for sid,lanes in turn_lanes.items():turn_ids.update((sid,i) for i in lanes.get('proxy',next(iter(lanes.values()))))
        for sid,lanes in user_lanes.items():user_ids.update((sid,i) for i in lanes.get('core',next(iter(lanes.values()))))
        totals={k:None for k in METRICS};reported=Counter();selected=[];ambiguities=[];by_model=defaultdict(lambda:{'records':0,'usage':{k:None for k in METRICS}})
        for session,lanes in usage_lanes.items():
            # Multiple captures of one native session are not summed. The chosen
            # lane is explicit, with alternatives and partial coverage disclosed.
            lane=next((x for x in ('proxy','claude-jsonl','codex-jsonl','otlp-json','declared') if x in lanes),sorted(lanes)[0])
            selected.append({'session_id':session,'source':lane,'records':len(lanes[lane])})
            if len(lanes)>1:ambiguities.append({'session_id':session,'chosen':lane,'excluded':sorted(set(lanes)-{lane}),'reason':'avoid potentially duplicated token accounting'})
            for a in lanes[lane]:
                model_usage=by_model[a.get('model') or 'unknown'];model_usage['records']+=1
                for k in METRICS:
                    v=a['usage'].get(k)
                    if type(v) in (int,float) and v>=0:
                        totals[k]=(totals[k] or 0)+v;reported[k]+=1;model_usage['usage'][k]=(model_usage['usage'][k] or 0)+v
        observed_calls=sum(x['records'] for x in selected)
        overhead_row=self.db.execute('SELECT total_ns,samples FROM run_overhead WHERE run_id=?',(run_id,)).fetchone()
        snapshot=self.db.execute('SELECT body FROM snapshots WHERE hash=?',(run['manifest'].get('config_snapshot'),)).fetchone()
        return {'run':run,'configuration':json.loads(snapshot[0]) if snapshot else None,'intercepts':intercepts,'verdicts':dict(effects),'events':sum(kinds.values()),'kinds':dict(kinds),
                'goal_evaluations':{k:dict(v) for k,v in goals.items()},'goal_outcomes':goal_outcomes,'drift':drift,
                'tools':dict(tools),'tool_outcomes':dict(tool_outcomes),'denied_then_observed_executing':len(tool_denials & tool_executions),'observed_agent_ids':sorted(agent_ids),'models':dict(models),'learning':dict(learn),'context_cache':dict(cache),
                'observed_model_turns':len(turn_ids) or None,'observed_user_turns':len(user_ids) or None,
                'elapsed_seconds':(run['finished_ns']-run['started_ns'])/1e9 if run['finished_ns'] else None,
                'observed_span_seconds':(last-first)/1e9 if first is not None else None,
                'events_outside_declared_run_window':bool(first is not None and (first<run['started_ns'] or (run['finished_ns'] is not None and last>run['finished_ns']))),
                'classifier_calls':classifier_calls,'supervisor_usage':supervisor_usage,'policy_hashes':sorted(x for x in policy_hashes if x),'logging_overhead_ms':overhead_row[0]/1e6 if overhead_row else None,'evaluation_overhead_ms':overhead,'usage':totals,'usage_reporting_counts':dict(reported),'usage_records':observed_calls,
                'usage_by_model':dict(by_model),'task_types':dict(task_types),'observed_skills':sorted(skill_ids),'usage_sources':selected,'usage_ambiguities':ambiguities,'missing_source_records':missing_sources,
                'context_edges':edges[:1000],'edges_truncated':len(edges)>1000,'coverage':dict(coverage),
                'interpretation':['Verdicts are not proof of host enforcement or causally prevented drift.',
                                  'Turn counts include observed model requests/imported assistant turns, not hidden reasoning.',
                                  'Unknown token/cost fields stay null; subset counters are not added to totals.',
                                  'Usage is observed coverage, not a claim of complete subscription billing.',
                                  'Evaluation overhead excludes hook process startup and trace-storage overhead.']}

    def compare(self,ids):
        if len(ids)<2 or len(ids)>10:raise ValueError('Compare 2 to 10 runs')
        reports=[self.report(i) for i in ids];base=reports[0]['run']['manifest'];differences=[]
        for r in reports[1:]:
            changes={k:{'baseline':base.get(k),'comparison':r['run']['manifest'].get(k)} for k in set(base)|set(r['run']['manifest']) if base.get(k)!=r['run']['manifest'].get(k)}
            def flatten(v,prefix=''):
                if isinstance(v,dict):
                    out={}
                    for k,item in v.items():out.update(flatten(item,prefix+'.'+k if prefix else k))
                    return out
                return {prefix:v}
            left=flatten(reports[0].get('configuration'));right=flatten(r.get('configuration'))
            config_changes={k:{'baseline':left.get(k),'comparison':right.get(k)} for k in set(left)|set(right) if left.get(k)!=right.get(k)}
            differences.append({'run_id':r['run']['id'],'changed_variables':changes,'configuration_changes':config_changes})
        return {'reports':reports,'differences':differences,'causal_claim':False,'note':'Descriptive comparison only. Outcomes and changed variables require review.'}
