"""CLI adapters for optional packages. No implementation is vendored into core."""
from __future__ import annotations
import copy
import importlib.metadata
import json
import os
import pathlib
import time
import uuid
from .host import merge, resolve, project_root, validate
from . import host as config_host
from .defaults import DEFAULT_PLUGINS
from .ports import trace_repository,publish_component
from gw_supervisor.api import read_json,write_json,digest


def add_arguments(sub):
    for name in ('trace','learn','sync'):
        p=sub.add_parser(name,help='Optional '+name+' plugin; command help is available when installed')
        p.add_argument('--project',default='.')
        p.add_argument('--client',default='generic')
        p.add_argument('arguments',nargs=__import__('argparse').REMAINDER)
    sub.add_parser('plugins',help='List optional plugin configuration and installation status')


def configure(home,family,*,mode=None,preview_chars=None):
    path=home/'config.json';existing=read_json(path,{'version':1})
    addition={'plugins':{family:{'enabled':True}}}
    if mode:addition['mode']=mode
    if preview_chars is not None:addition['plugins'][family]['preview_chars']=preview_chars
    new=merge(existing,addition)
    validate(merge(config_host.DEFAULTS,{k:v for k,v in new.items() if k!='clients'}))
    for client in new.get('clients',{}):validate(merge(merge(config_host.DEFAULTS,{k:v for k,v in new.items() if k!='clients'}),new['clients'][client]))
    if path.exists():write_json(home/'backups'/('plugins-'+digest(existing)+'.json'),existing)
    write_json(path,new)


def learning_context(home, project, lookback):
    from .ports import Store
    repository = Store(home)
    try:
        return repository.learning_evidence(project, lookback)
    finally:
        repository.close()


def run(args,home,output):
    config,_=resolve(home,project_root(args.project) if hasattr(args,'project') else pathlib.Path.cwd(),'generic')
    if args.cmd=='plugins':
        result={}
        for name,package in [('observe','gw-observe'),('learning','gw-learning'),('sync','gw-sync')]:
            try:version=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:version=None
            result[name]={'installed_version':version,**config['plugins'][name]}
        return output(result)
    family={'trace':'observe','learn':'learning','sync':'sync'}[args.cmd]
    module={'trace':'gw_observe.cli','learn':'gw_learning.cli','sync':'gw_sync.cli'}[args.cmd]
    try:cli=__import__(module,fromlist=['parser'])
    except ImportError as exc:raise ValueError('Install the optional packages with the installer --plugins flag') from exc
    argv=list(args.arguments)
    if args.cmd=='trace' and argv and argv[0]=='init':
        import argparse
        p=argparse.ArgumentParser(prog='gw trace init');p.add_argument('--baseline',action='store_true');p.add_argument('--mode',choices=['baseline','enforce','observe']);p.add_argument('--preview-chars',type=int,default=0)
        selected=p.parse_args(argv[1:])
        configure(home,'observe',mode='baseline' if selected.baseline else selected.mode,preview_chars=selected.preview_chars)
        return output({'enabled':True,'mode':selected.mode or ('baseline' if selected.baseline else config['mode']),
                       'inference_calls':0,'next':'Start a fresh agent session. Baseline does not evaluate or apply GW policy.'})
    parsed=cli.parser().parse_args(argv)
    project=str(project_root(args.project));config,_=resolve(home,pathlib.Path(project),args.client)
    directory=config['plugins'][family]['options'].get('directory',str(home/('observability' if family=='observe' else family)))
    if args.cmd=='trace':
        if parsed.command=='serve':
            from gw_observe.server import serve
            serve(directory,parsed.port,parsed.open,repository_factory=lambda:trace_repository(home,config))
            return output({'stopped':True})
        with trace_repository(home,config) as repo:
            if parsed.command=='start':
                if parsed.project=='.':parsed.project=project
            return output(cli.run(parsed,repo,config=config))
    identity={'project':project,'client':args.client,'session':args.cmd+'-'+uuid.uuid4().hex,'run_id':os.environ.get('GW_RUN_ID')}
    def observe(kind,attrs,start,end):publish_component(home,config,identity,kind,attrs,start_ns=start,end_ns=end)
    if args.cmd=='learn':
        from gw_learning.engine import LearningCoordinator
        if config['plugins']['learning']['provider']!='local':raise ValueError('Custom learning coordinators must be invoked through their installed adapter; local plugins are configurable independently')
        with LearningCoordinator(directory,observer=observe) as coordinator:
            if parsed.command=='init':configure(home,'learning')
            elif not config['plugins']['learning']['enabled']:raise ValueError('Learning is disabled; run gw learn init')
            context=learning_context(home,project,coordinator.config()['lookback_days']) if parsed.command in {'run','tick'} else None
            if parsed.command=='watch':context=lambda:learning_context(home,project,coordinator.config()['lookback_days'])
            return output(cli.run(parsed,coordinator,context))
    from gw_sync.store import open_provider,SyncWorkspace
    if parsed.command=='init':
        path=home/'config.json';existing=read_json(path,{'version':1})
        overlay={'plugins':{'sync':{'enabled':True,'provider':parsed.provider}}}
        if parsed.options:overlay['plugins']['sync']['options']={'provider_options':read_json(pathlib.Path(parsed.options))}
        if parsed.provider!='local' and not parsed.options:raise ValueError('Remote sync requires an explicit --options file')
        if parsed.provider!='local' and parsed.repository:raise ValueError('Remote adapters use provider options, not --repository')
        if parsed.repository:overlay['plugins']['sync']['options']={'repository':str(pathlib.Path(parsed.repository).expanduser().resolve())}
        candidate=merge(existing,overlay)
        for client in {'generic',*candidate.get('clients',{})}:
            validate(merge(merge(config_host.DEFAULTS,{k:v for k,v in candidate.items() if k!='clients'}),candidate.get('clients',{}).get(client,{})))
        if path.exists():write_json(home/'backups'/('plugins-'+digest(existing)+'.json'),existing)
        write_json(path,candidate)
        return output({'enabled':True,'repository':parsed.repository or str(pathlib.Path(directory)/'repository'),'automatic_activation':False})
    if not config['plugins']['sync']['enabled']:raise ValueError('Sync is disabled; run gw sync init')
    opts=config['plugins']['sync']['options']
    provider_options={'directory':opts.get('repository',str(pathlib.Path(directory)/'repository'))} if config['plugins']['sync']['provider']=='local' else opts.get('provider_options',{})
    provider=open_provider(config['plugins']['sync']['provider'],provider_options)
    with SyncWorkspace(provider,directory,observer=observe) as store:
        return output(cli.run(parsed,store))
