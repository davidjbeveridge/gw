"""Optional wrapper over the standard knowledge adapter. Never retains content."""
import time
from .contract import digest


class ObservedKnowledgeProvider:
    def __init__(self,provider,emit):self.provider,self.emit=provider,emit
    def capabilities(self):return self.provider.capabilities()
    def _call(self,method,*args,**kwargs):
        start=time.time_ns(); attrs={'operation':method};result=None
        try:
            result=getattr(self.provider,method)(*args,**kwargs)
            attrs['status']='success'
            if isinstance(result,dict):
                if 'hits' in result:attrs.update(hits=len(result['hits']),revision=result.get('revision'))
                if 'document_id' in result:attrs.update(document_id=result['document_id'],revision=result.get('revision'))
                if 'text' in result:attrs['returned_chars']=len(result['text'])
                if result.get('revision'):attrs['source_ref']='knowledge:'+str(result.get('document_id','corpus'))+':'+result['revision']
            return result
        except Exception as exc:
            attrs.update(status='error',error=type(exc).__name__);raise
        finally:self.emit('knowledge.'+method,attrs,start,time.time_ns())
    def revision(self,scope):return self._call('revision',scope)
    def search(self,request):return self._call('search',request)
    def read(self,request):return self._call('read',request)
    def put(self,*a,**kw):return self._call('put',*a,**kw)
    def delete(self,*a,**kw):return self._call('delete',*a,**kw)
    def export(self,*a,**kw):
        start=time.time_ns();count=0;status='success'
        try:
            for record in self.provider.export(*a,**kw):
                count+=1;yield record
        except Exception:
            status='error';raise
        finally:self.emit('knowledge.export',{'records':count,'status':status},start,time.time_ns())
    def rebuild_index(self):return self._call('rebuild_index')


class ObservedContextCache:
    def __init__(self,cache,emit):self.cache,self.emit=cache,emit
    def assemble(self,provider,request,**kwargs):
        start=time.time_ns();attrs={'query_hash':digest(request.to_dict())}
        try:
            packet=self.cache.assemble(provider,request,**kwargs)
            attrs.update(status='success',cache_hit=packet['cache']['hit'],cache_stored=packet['cache']['stored'],
                freshness=packet['cache']['freshness'],revision=packet.get('revision'),evidence_chars=packet['evidence_chars'],
                documents=[{'id':p['document_id'],'revision':p['revision'],'start_char':p['start_char'],'end_char':p['end_char']} for p in packet['evidence']],
                truncated=packet['truncated'],miss_reason=packet['cache'].get('miss_reason'))
            return packet
        except Exception as exc:attrs.update(status='error',error=type(exc).__name__);raise
        finally:self.emit('knowledge.context',attrs,start,time.time_ns())
    def stats(self):return self.cache.stats()
    def clear(self,*a,**kw):
        start=time.time_ns();result=self.cache.clear(*a,**kw)
        self.emit('knowledge.cache_clear',result,start,time.time_ns());return result
