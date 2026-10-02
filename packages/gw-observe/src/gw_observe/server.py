"""Read-only local dashboard. Registered source IDs only; never arbitrary paths."""
import hmac
import importlib.resources
import json
import pathlib
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from socketserver import TCPServer
from .contract import canonical,private_dir
from .store import LocalTraceRepository


def make_server(directory,port=0,repository_factory=None):
    directory=private_dir(directory);key=directory/'dashboard-token'
    if key.is_symlink():raise ValueError('Dashboard token cannot be a symlink')
    if not key.exists():
        try:
            fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
        except FileExistsError:pass
    token=key.read_text().strip()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def setup(self):super().setup();self.connection.settimeout(10)
        def respond(self,status,body,content_type='application/json'):
            data=body if isinstance(body,bytes) else canonical(body).encode()
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            host=self.headers.get('Host','')
            if host not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
                return self.respond(403,{'error':'untrusted_host'})
            u=urllib.parse.urlsplit(self.path)
            if u.path in {'/','/app.js','/style.css'}:
                file='index.html' if u.path=='/' else u.path[1:]
                data=importlib.resources.files('gw_observe').joinpath('web',file).read_bytes()
                return self.respond(200,data,{'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}[file])
            try:authorized=hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
            except TypeError:authorized=False
            origin=self.headers.get('Origin')
            if not authorized or (origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}):
                return self.respond(401,{'error':'unauthorized'})
            q=urllib.parse.parse_qs(u.query)
            try:
                with (repository_factory() if repository_factory else LocalTraceRepository(directory)) as repo:
                    if u.path=='/api/runs':result=repo.runs(200)
                    elif u.path.startswith('/api/report/'):result=repo.report(u.path.split('/')[-1])
                    elif u.path.startswith('/api/event/'):result=repo.event(u.path.split('/')[-1])
                    elif u.path.startswith('/api/timeline/'):
                        result=repo.timeline(u.path.split('/')[-1],offset=int(q.get('offset',['0'])[0]))
                    elif u.path=='/api/compare':result=repo.compare(q.get('id',[]))
                    else:return self.respond(404,{'error':'not_found'})
                return self.respond(200,result)
            except (ValueError,KeyError):return self.respond(400,{'error':'invalid_request'})
            except Exception:return self.respond(503,{'error':'trace_store_unavailable'})
        def do_POST(self):self.respond(405,{'error':'read_only_dashboard'})
    class Server(ThreadingHTTPServer):
        def server_bind(self):
            TCPServer.server_bind(self);self.server_name='127.0.0.1';self.server_port=self.server_address[1]
    server=Server(('127.0.0.1',port),Handler);server.token=token
    return server


def serve(directory,port=7789,open_browser=False,repository_factory=None):
    server=make_server(directory,port,repository_factory);url=f'http://127.0.0.1:{server.server_port}/'
    if open_browser:
        import webbrowser
        webbrowser.open(url+'#token='+server.token)
    print(f'GW observability: {url} (read-only). Token file: {pathlib.Path(directory)/"dashboard-token"}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
