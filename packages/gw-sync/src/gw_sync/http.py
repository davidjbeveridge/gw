"""Authenticated bundle transport. Reference server owns SQLite on its local disk.

Serve behind an authenticated TLS ingress for off-machine access. There is no
remote shell, arbitrary file read, or automatic harness activation operation.
"""
from __future__ import annotations
import base64
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from socketserver import TCPServer
from .store import PROTOCOL,MAX_FILE,LocalBundleStore,canonical,sha

MAX_BODY=16*1024*1024

class HttpBundleProvider:
    def __init__(self,endpoint,*,key_env='GW_SYNC_TOKEN',timeout_seconds=10):
        u=urllib.parse.urlsplit(endpoint)
        if not u.hostname or u.username or u.password or u.query or u.fragment or (u.scheme!='https' and not(u.scheme=='http' and u.hostname in {'127.0.0.1','localhost','::1'})):
            raise ValueError('Use a complete HTTPS or loopback endpoint without embedded credentials')
        if type(timeout_seconds) not in (int,float) or not 0<timeout_seconds<=30:raise ValueError('Invalid timeout')
        self.endpoint,self.key_env,self.timeout=endpoint,key_env,timeout_seconds
    def call(self,method,request):
        token=os.environ.get(self.key_env,'')
        if len(token)<20 or any(x.isspace() for x in token):raise ValueError('Missing or invalid sync credential')
        body=canonical({'protocol':PROTOCOL,'method':method,'request':request}).encode()
        if len(body)>MAX_BODY:raise ValueError('Bundle request too large')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*a,**k):raise ValueError('Sync redirects refused')
        req=urllib.request.Request(self.endpoint,body,{'Content-Type':'application/json','Authorization':'Bearer '+token})
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=self.timeout) as response:data=response.read(MAX_BODY+1)
        except urllib.error.HTTPError as exc:raise ValueError('Bundle service rejected the operation (HTTP '+str(exc.code)+')') from None
        if len(data)>MAX_BODY:raise ValueError('Bundle response too large')
        result=json.loads(data)
        if not isinstance(result,dict) or set(result)!={'protocol','result'} or result['protocol']!=PROTOCOL:raise ValueError('Invalid bundle response contract')
        return result['result']
    def put_blob(self,data):
        if not isinstance(data,bytes) or len(data)>MAX_FILE:raise ValueError('Invalid blob')
        result=self.call('put_blob',{'data':base64.b64encode(data).decode('ascii')})
        if result.get('hash')!=sha(data):raise ValueError('Remote blob hash mismatch')
        return result['hash']
    def get_blob(self,h):
        result=self.call('get_blob',{'hash':h});data=base64.b64decode(result['data'],validate=True)
        if len(data)>MAX_FILE or sha(data)!=h:raise ValueError('Remote blob hash mismatch')
        return data
    def publish(self,manifest,*,channel,expected=None):
        return self.call('publish',{'manifest':manifest,'channel':channel,'expected':expected})
    def resolve(self,reference):return self.call('resolve',{'reference':reference})


def make_server(directory,token,port=0,*,writable=False):
    if not isinstance(token,str) or len(token)<20 or any(x.isspace() for x in token):raise ValueError('Provision a private token of at least 20 characters')
    with LocalBundleStore(directory):pass
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def setup(self):super().setup();self.connection.settimeout(15)
        def reply(self,status,body):
            data=canonical(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(401,{'error':'unauthorized'})
            if self.path!='/v1/bundles':return self.reply(404,{'error':'not_found'})
            try:
                size=int(self.headers.get('Content-Length','-1'))
                if not 0<=size<=MAX_BODY or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Invalid body')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict) or set(body)!={'protocol','method','request'} or body['protocol']!=PROTOCOL:raise ValueError('Invalid envelope')
                method,request=body['method'],body['request']
                fields={'put_blob':{'data'},'get_blob':{'hash'},'publish':{'manifest','channel','expected'},'resolve':{'reference'}}
                if method not in fields or not isinstance(request,dict) or set(request)!=fields[method]:raise ValueError('Invalid operation')
                if method in {'put_blob','publish'} and not writable:return self.reply(403,{'error':'read_only'})
                with LocalBundleStore(directory) as store:
                    if method=='put_blob':result={'hash':store.put_blob(base64.b64decode(request['data'],validate=True))}
                    elif method=='get_blob':result={'data':base64.b64encode(store.get_blob(request['hash'])).decode('ascii')}
                    elif method=='publish':result=store.publish(request['manifest'],channel=request['channel'],expected=request['expected'])
                    else:result=store.resolve(request['reference'])
                self.reply(200,{'protocol':PROTOCOL,'result':result})
            except (ValueError,KeyError,TypeError,OSError):self.reply(409,{'error':'invalid_or_conflicting_operation'})
            except Exception:self.reply(503,{'error':'bundle_store_unavailable'})
    class Server(ThreadingHTTPServer):
        def server_bind(self):TCPServer.server_bind(self);self.server_name='127.0.0.1';self.server_port=self.server_address[1]
    return Server(('127.0.0.1',port),Handler)
