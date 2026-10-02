import argparse
import json
import pathlib
import time
from .engine import LearningCoordinator,DEFAULTS,canonical


def parser():
    p=argparse.ArgumentParser(prog='gw-learning')
    p.add_argument('--directory',default=str(pathlib.Path.home()/'.local/share/gw-learning'))
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--config',help='Explicit configuration JSON; otherwise safe defaults');init.add_argument('--mode',choices=['off','propose','auto']);init.add_argument('--lookback-days',type=int);init.add_argument('--strategies',help='thematic,expansion')
    run=sub.add_parser('run');run.add_argument('--input',help='Evidence metadata JSON; never a hidden transcript scan')
    tick=sub.add_parser('tick');tick.add_argument('--input')
    watch=sub.add_parser('watch');watch.add_argument('--interval',type=int,default=3600)
    sub.add_parser('list')
    show=sub.add_parser('show');show.add_argument('id')
    for name in ('approve','reject','execute'):
        c=sub.add_parser(name);c.add_argument('id')
    promote=sub.add_parser('publish');promote.add_argument('id');promote.add_argument('--destination',required=True)
    return p


def run(args,coordinator,context=None):
    if args.command=='init':
        config=json.loads(pathlib.Path(args.config).read_text()) if args.config else json.loads(canonical(DEFAULTS))
        if args.mode:config['mode']=args.mode
        if args.lookback_days:config['lookback_days']=args.lookback_days
        if args.strategies:config['strategies']=args.strategies.split(',')
        return coordinator.configure(config)
    if args.command in {'run','tick'}:
        c=json.loads(pathlib.Path(args.input).read_text()) if args.input else (context or {})
        return coordinator.run(c)
    if args.command=='list':return coordinator.list()
    if args.command=='show':return coordinator.get(args.id)
    if args.command in {'approve','reject'}:return coordinator.review(args.id,args.command=='approve')
    if args.command=='execute':return coordinator.execute(args.id)
    if args.command=='publish':return coordinator.promote(args.id,args.destination)
    if args.command=='watch':
        if args.interval<60:raise ValueError('Polling interval must be at least 60 seconds')
        try:
            while True:
                print(canonical(coordinator.run(context() if callable(context) else context or {})),flush=True);time.sleep(args.interval)
        except KeyboardInterrupt:return {'stopped':True}


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        with LearningCoordinator(args.directory) as c:print(canonical(run(args,c)))
    except (ValueError,OSError) as exc:raise SystemExit(type(exc).__name__+': learning command failed; inspect configuration and proposal state')
