import argparse
import json
import pathlib
import os
from .store import LocalBundleStore,pack,plan,apply,canonical


def parser():
    p=argparse.ArgumentParser(prog='gw-sync')
    p.add_argument('--store',default=str(pathlib.Path.home()/'.local/share/gw-sync'))
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--repository',help='Local bundle repository directory');init.add_argument('--provider',default='local');init.add_argument('--options',help='Remote provider options JSON file, credential references only')
    push=sub.add_parser('push');push.add_argument('--root',default='.');push.add_argument('--include',action='append',required=True)
    push.add_argument('--channel',required=True);push.add_argument('--expected')
    preview=sub.add_parser('plan');preview.add_argument('reference');preview.add_argument('--destination',required=True);preview.add_argument('--output')
    use=sub.add_parser('apply');use.add_argument('plan_file')
    get=sub.add_parser('show');get.add_argument('reference')
    sub.add_parser('history')
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=7791);serve.add_argument('--token-env',default='GW_SYNC_TOKEN');serve.add_argument('--writable',action='store_true')
    return p


def dispatch(args,store):
    if args.command=='serve':
        from .http import make_server
        directory=store.directory if hasattr(store,'directory') else store.provider.directory
        server=make_server(directory,os.environ.get(args.token_env,''),args.port,writable=args.writable)
        print('Bundle service on 127.0.0.1:'+str(server.server_port),flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
        return {'stopped':True}
    if args.command=='init':return {'ready':True,'automatic_activation':False}
    if args.command=='push':return pack(store,args.root,args.include,channel=args.channel,expected=args.expected)
    if args.command=='show':return store.resolve(args.reference)
    if args.command=='history':return store.history()
    if args.command=='plan':
        result=plan(store,args.reference,args.destination)
        with store.db:store._journal('planned',{'reference':result['reference'],'plan_hash':result['plan_hash'],'conflicts':result['conflicts'],'files':len(result['changes'])})
        if args.output:
            with pathlib.Path(args.output).open('x',encoding='utf-8') as f:f.write(canonical(result))
        return result
    if args.command=='apply':return apply(store,json.loads(pathlib.Path(args.plan_file).read_text()))


def run(args,store):
    try:return dispatch(args,store)
    except Exception as exc:
        with store.db:store._journal('operation_failed',{'operation':args.command,'error':type(exc).__name__})
        raise


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        with LocalBundleStore(args.store) as store:print(canonical(run(args,store)))
    except (ValueError,OSError) as exc:raise SystemExit(type(exc).__name__+': sync failed; review the manifest, expected revision and destination')
