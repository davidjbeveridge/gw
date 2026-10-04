"""Bounded pre/post-fix diagnostic. No agents, models or network requests."""
import argparse, copy, json, os, pathlib, random, statistics, subprocess, sys, tempfile, time
ROOT=pathlib.Path(os.environ.get('GW_BENCH_OUT','gw-perf-results'));ROOT.mkdir(exist_ok=True)
PYTHON=os.environ['GW_BENCH_PYTHON']
SITES={'before':os.environ['GW_BENCH_BEFORE_SITE'],'after':os.environ['GW_BENCH_AFTER_SITE']}

def stats(samples):
 s=sorted(samples);return {'n':len(s),'median_ms':statistics.median(s),'p95_ms':s[min(len(s)-1,int(len(s)*.95))]}

def event(p,i,phase='tool.before',session='measured'):
 return {'client':'claude','session':session,'project':str(p),'type':phase,'id':str(i),'tool':'Read','input':{'file_path':f'fixture-{i%32}.py'},**({'success':True,'output':'fixture'} if phase=='tool.after' else {})}

def worker(variant,home,project,history,trace,warm=False):
 sys.path.insert(0,SITES[variant])
 from gw_supervisor.engine import Supervisor
 from gw_supervisor.util import canonical,digest,write_json
 h,p=pathlib.Path(home),pathlib.Path(project);p.mkdir(exist_ok=True);(p/'.git').mkdir(exist_ok=True)
 if not warm:
  write_json(h/'config.json',{'plugins':{'observe':{'enabled':trace}}})
  with Supervisor(h) as s:
   s.store.set_task(str(p),'Inspect fixtures; do not deploy.')
   sessions=[s.session_context(event(p,0,session='history-'+str(i))) for i in range(10)]
   exemplar=s.evaluate(event(p,0,session='history-0'))
   with s.store.db:
    s.store.db.execute('DELETE FROM events')
    rows=[]
    for i in range(history):
     sess=sessions[i%10];e=event(p,i,'tool.after' if i%2 else 'tool.before')
     rows.append((sess['id'],'seed'+str(i),e['type'],digest([e['tool'],e['input']]),'Read',1 if i%2 else None,canonical({**exemplar,'session_id':sess['id']}),time.time()-history+i))
    s.store.db.executemany('INSERT INTO events VALUES (?,?,?,?,?,?,?,?)',rows)
   s.store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 else:
  timings=[]
  with Supervisor(h) as s: # deliberately no externally supplied scope
   for i in range(65):
    started=time.perf_counter_ns();r=s.evaluate(event(p,10000+i,session='warm'))
    assert not r.get('plugin_errors') and r['decision']=='allow',r
    if i>=5:timings.append((time.perf_counter_ns()-started)/1e6)
  print(json.dumps({'warm':stats(timings),'samples_ms':timings}))

if len(sys.argv)>1:
 args=json.loads(sys.argv[1]);worker(**args);raise SystemExit
randomizer=random.Random(71411);results=[];raw=[]
with tempfile.TemporaryDirectory(prefix='gw-regression-perf-') as tmp:
 root=pathlib.Path(tmp);p=root/'project';p.mkdir()
 for history in (0,10000):
  for trace in (False,True):
   homes={v:root/(v+'-'+str(history)+'-'+str(trace)) for v in SITES}
   envs={v:{**os.environ,'PYTHONPATH':SITES[v]} for v in SITES}
   for v in SITES:
    spec=dict(variant=v,home=str(homes[v]),project=str(p),history=history,trace=trace)
    subprocess.run([PYTHON,__file__,json.dumps(spec)],check=True,env=envs[v],capture_output=True,timeout=30)
   timed={v:[] for v in SITES}
   for block in range(35):
    order=list(SITES);randomizer.shuffle(order)
    for v in order:
     proposal={'session_id':'measured','cwd':str(p),'tool_use_id':str(block),'tool_name':'Read','tool_input':{'file_path':f'fixture-{block%32}.py'}}
     started=time.perf_counter_ns()
     for phase in ('pre','post'):
      native={**proposal,**({'tool_response':{'content':'fixture'}} if phase=='post' else {})}
      proc=subprocess.run([PYTHON,'-m','gw_supervisor','--home',str(homes[v]),'hook','claude',phase],input=json.dumps(native),text=True,capture_output=True,check=True,env=envs[v],timeout=10)
      assert 'unavailable' not in proc.stdout and json.loads(proc.stdout).get('hookSpecificOutput',{}).get('permissionDecision') not in ('deny','ask'),proc.stdout
     ms=(time.perf_counter_ns()-started)/1e6
     if block>=5:
      timed[v].append(ms);raw.append({'variant':v,'history':history,'trace':trace,'block':block-5,'pair_ms':ms})
   for v in SITES:
    spec=dict(variant=v,home=str(homes[v]),project=str(p),history=history,trace=trace,warm=True)
    warm=json.loads(subprocess.check_output([PYTHON,__file__,json.dumps(spec)],env=envs[v],timeout=30))
    results.append({'variant':v,'history':history,'trace':trace,'native_pair':stats(timed[v]),**warm})
   (ROOT/'results.json').write_text(json.dumps({'reference_commit':'4aa76c63c64eef1aa97a1927a4424670d000e994','scope':'Synthetic hook/runtime regression; no live agents, no model requests; shared Linux/Python 3.13 environment','native_measured_pairs_per_variant':30,'warm_events_per_variant':60,'seed':71411,'results':results,'native_samples':raw},indent=2))
   print(history,trace,results[-2]['native_pair'],results[-1]['native_pair'],flush=True)
