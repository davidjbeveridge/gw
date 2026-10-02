"""Inspect, compare and export recorded runs; never orchestrates a benchmark."""
import argparse
import json
import pathlib
import time
import uuid
from .contract import canonical
from .store import LocalTraceRepository


def parser():
    p=argparse.ArgumentParser(prog='gw-observe')
    p.add_argument('--directory',default=str(pathlib.Path.home()/'.local/share/gw-observe'))
    sub=p.add_subparsers(dest='command',required=True)
    start=sub.add_parser('start');start.add_argument('--name',default='Agent run');start.add_argument('--project',default='.')
    start.add_argument('--harness',required=True);start.add_argument('--harness-version');start.add_argument('--model')
    start.add_argument('--prompt-file');start.add_argument('--capture-prompt',action='store_true');start.add_argument('--bind',action='store_true')
    start.add_argument('--client');start.add_argument('--metadata',help='JSON file with additional experiment variables')
    finish=sub.add_parser('finish');finish.add_argument('id');finish.add_argument('--outcome',choices=['succeeded','failed','partial','cancelled','unknown'],default='unknown');finish.add_argument('--evidence')
    ls=sub.add_parser('runs');ls.add_argument('--limit',type=int,default=100)
    for name in ('show','timeline'):
        a=sub.add_parser(name);a.add_argument('id',nargs='?',default='latest')
        if name=='timeline':a.add_argument('--offset',type=int,default=0);a.add_argument('--limit',type=int,default=200)
    record=sub.add_parser('record');record.add_argument('file',help='Explicit gw.observation/1 metadata envelope')
    note=sub.add_parser('outcome');note.add_argument('--run',required=True);note.add_argument('--goal',required=True)
    note.add_argument('--value',choices=['met','not_met','unknown'],required=True);note.add_argument('--evidence',required=True)
    compare=sub.add_parser('compare');compare.add_argument('ids',nargs='+')
    event=sub.add_parser('event');event.add_argument('id');event.add_argument('--source',action='store_true')
    imp=sub.add_parser('import');imp.add_argument('file');imp.add_argument('--run',required=True);imp.add_argument('--format',choices=['claude-jsonl','codex-jsonl'],required=True);imp.add_argument('--session')
    export=sub.add_parser('export-otlp');export.add_argument('ids',nargs='+');export.add_argument('--output');export.add_argument('--endpoint');export.add_argument('--key-env');export.add_argument('--headers-env')
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=7789);serve.add_argument('--open',action='store_true')
    return p


def resolve(repo,value):
    if value=='latest':
        rows=repo.runs(1)
        if not rows:raise ValueError('No recorded runs')
        return rows[0]['id']
    return value


def run(args,repo,*,config=None):
    command=args.command
    if command=='record':
        file=pathlib.Path(args.file)
        if file.stat().st_size>32768:raise ValueError('Observation file exceeds budget')
        return {'inserted':repo.record(json.loads(file.read_text(encoding='utf-8')))}
    if command=='outcome':
        rid=resolve(repo,args.run);now=time.time_ns()
        return {'inserted':repo.record({'protocol':'gw.observation/1','id':uuid.uuid4().hex,'run_id':rid,'kind':'goal.outcome',
            'start_ns':now,'end_ns':now,'attributes':{'goal_id':args.goal,'value':args.value,'evidence_ref':args.evidence,'basis':'operator_asserted'},'source':{}})}
    if command=='runs':return repo.runs(args.limit)
    if command=='start':
        metadata=json.loads(pathlib.Path(args.metadata).read_text()) if args.metadata else {}
        return repo.start(args.name,args.project,harness=args.harness,harness_version=args.harness_version,model=args.model,
                          prompt_file=args.prompt_file,capture_prompt=args.capture_prompt,bind=args.bind,client=args.client,
                          metadata=metadata,config=config,mode=(config or {}).get('mode','trace_only'))
    if command=='finish':return repo.finish(resolve(repo,args.id),args.outcome,args.evidence)
    if command=='show':return repo.report(resolve(repo,args.id))
    if command=='timeline':return repo.timeline(resolve(repo,args.id),offset=args.offset,limit=args.limit)
    if command=='compare':return repo.compare([resolve(repo,i) for i in args.ids])
    if command=='event':return repo.event(args.id,resolve_source=args.source)
    if command=='import':
        from .importers import import_transcript
        return import_transcript(repo,resolve(repo,args.run),args.file,args.format,session_id=args.session)
    if command=='export-otlp':
        from .otlp import export,send
        payload=export(repo,[resolve(repo,i) for i in args.ids])
        if args.output:
            with pathlib.Path(args.output).open('x',encoding='utf-8') as f:f.write(canonical(payload))
        if args.endpoint:return send(payload,args.endpoint,key_env=args.key_env,headers_env=args.headers_env)
        return {'written':args.output,'format':'OTLP/HTTP JSON','content_included':False} if args.output else payload
    if command=='serve':
        from .server import serve
        serve(repo.directory,args.port,args.open);return {'stopped':True}


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        with LocalTraceRepository(args.directory) as repo:print(canonical(run(args,repo)))
    except (ValueError,OSError) as exc:raise SystemExit(type(exc).__name__+': observation command failed; inspect run IDs, sources, and configuration')
