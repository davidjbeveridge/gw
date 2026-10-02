"""Optional plugin boundaries. Core remains usable without any plugin installed.

Plugin factories are trusted operator-installed code, never worktree imports.
Observability failures do not turn a verdict into permission or call a model.
"""
from __future__ import annotations
import copy
import importlib.metadata
import os
import pathlib
import time
from typing import Protocol
from .util import canonical, digest, redact

PLUGIN_PROTOCOL = 'gw.plugins/1'
DEFAULT_PLUGINS = {
    'observe': {'enabled':False,'provider':'local','options':{},'preview_chars':0},
    'learning': {'enabled':False,'provider':'local','options':{}},
    'sync': {'enabled':False,'provider':'local','options':{}},
}


class ObservationSink(Protocol):
    def record(self, observation: dict) -> bool: ...


class LearningPlugin(Protocol):
    name: str
    version: str
    def propose(self, context: dict, settings: dict) -> list[dict]: ...


class BundleProvider(Protocol):
    def put_blob(self, data: bytes) -> str: ...
    def get_blob(self, content_hash: str) -> bytes: ...
    def publish(self, manifest: dict, *, channel: str, expected: str | None) -> dict: ...
    def resolve(self, reference: str) -> dict: ...


def validate_plugins(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULT_PLUGINS):raise ValueError('Unknown plugin family')
    for name,c in value.items():
        if not isinstance(c,dict) or set(c)-set(DEFAULT_PLUGINS[name]):raise ValueError('Unknown plugin setting')
        if type(c.get('enabled')) is not bool or not isinstance(c.get('options'),dict):raise ValueError('Invalid plugin settings')
        if not isinstance(c.get('provider'),str) or not c['provider']:raise ValueError('Plugin provider required')
        if name=='observe' and (type(c.get('preview_chars')) is not int or not 0<=c['preview_chars']<=2000):raise ValueError('Invalid preview limit')


def enabled(config):
    return config.get('plugins',{}).get('observe',{}).get('enabled',False)


def proposal(event,config):
    out={k:event[k] for k in ('tool','model','operation','parent_id','agent_id','task_type','tool_kind','skill_id') if k in event}
    if isinstance(event.get('input'),dict):
        out.update(input_hash=digest(redact(event['input'])),input_keys=sorted(event['input'])[:40])
        n=config.get('plugins',{}).get('observe',{}).get('preview_chars',0)
        if n:out['input_preview']=canonical(redact(event['input']))[:n]
    if event.get('native_trace_hint'):out['native_trace_hint']=event['native_trace_hint']
    return out


def usage_metadata(raw):
    """Keep only reported numeric counters, never arbitrary provider payloads."""
    if not isinstance(raw,dict):return None
    names={'input_tokens','output_tokens','prompt_tokens','completion_tokens','cached_input_tokens','reasoning_tokens',
           'cache_read_input_tokens','cache_creation_input_tokens','cache_write_input_tokens','reasoning_output_tokens','cost_usd'}
    import math
    out={k:v for k,v in raw.items() if k in names and type(v) in (int,float) and math.isfinite(v) and v>=0}
    for key in ('input_tokens_details','prompt_tokens_details','output_tokens_details','completion_tokens_details'):
        if isinstance(raw.get(key),dict):out[key]={k:v for k,v in raw[key].items() if k in {'cached_tokens','reasoning_tokens'} and type(v) is int and v>=0}
    return out


def tool_kind(event):
    explicit=event.get('tool_kind')
    if explicit in {'cli','mcp','api','script','browser','computer_use','native','unknown'}:
        return explicit,'host_declared'
    name=event.get('tool','').lower()
    # Hint only; MCP may carry browser/API actions. Preserve transport separately.
    if any(x in name for x in ('computer','mouse','desktop')):return 'computer_use','name_hint'
    if any(x in name for x in ('browser','playwright','chrome')):return 'browser','name_hint'
    if name.startswith('mcp'):return 'mcp','name_hint'
    if name in {'bash','shell','powershell','exec_command','terminal','run_command'}:return 'cli','name_hint'
    if name in {'read','write','edit','apply_patch','glob','grep'}:return 'native','name_hint'
    return 'unknown','unclassified'


def trace_repository(home,config):
    c=config.get('plugins',{}).get('observe',DEFAULT_PLUGINS['observe'])
    if c['provider']=='local':
        from gw_observe.store import LocalTraceRepository
        repo=LocalTraceRepository(c['options'].get('directory',str(home/'observability')),core_database=home/'state.sqlite3')
        for family,filename,kind in [('learning','learning.sqlite3','gw.learning'),('sync','channels.sqlite3','gw.sync')]:
            directory=config.get('plugins',{}).get(family,{}).get('options',{}).get('directory',str(home/family))
            repo.register_source(pathlib.Path(directory)/filename,kind,source_id='gw-'+family)
        return repo
    matches=list(importlib.metadata.entry_points(group='gw.observability',name=c['provider']))
    if len(matches)!=1:raise ValueError('Expected one installed observability provider')
    return matches[0].load()(copy.deepcopy(c['options']))


def publish_intercept(home,session,event,result):
    config=session['config']
    if not enabled(config):return
    trace_started=time.perf_counter_ns()
    try:
        with trace_repository(home,config) as repo:
            run=repo.bind_session(session['id'],event['project'],event['client'],run_id=event.get('run_id') or os.environ.get('GW_RUN_ID'),config=config)
            audit=result.get('audit',{});start=audit.get('start_ns',time.time_ns());end=audit.get('end_ns',start)
            attrs={'client':event['client'],'native_session':event['session'],'event_type':event['type'],'tool_call_id':event['id'] if event['type'].startswith('tool.') else None,'agent_id':event.get('agent_id'),'decision':result['decision'],
                   'model':event.get('model'),'tool':event.get('tool'),'skill_id':event.get('skill_id'),'task_type':event.get('task_type'),'success':event.get('success'), 'enforcement':'verdict_issued_not_execution_confirmation'}
            attrs['goal_index']=[{k:g[k] for k in ('id','status','effect','value','threshold','label') if k in g} for g in audit.get('goals',[])]
            attrs['alignment_observation']=audit.get('alignment_observation')
            attrs['policy_hash']=result.get('policy_hash')
            attrs['mode']=config.get('mode')
            if event['type']=='tool.before':attrs['tool_class'],attrs['tool_class_basis']=tool_kind(event)
            if event.get('tool','').lower().startswith('mcp'):attrs['transport']='mcp'
            observation={'protocol':'gw.observation/1','id':digest(['gw',session['id'],event['id'],event['type']]),'run_id':run,
                'session_id':session['id'],'parent_id':event.get('parent_id'),'kind':'gw.intercept','start_ns':start,'end_ns':end,
                'attributes':attrs,'source':{'source_id':'gw-core','session':session['id'],'event':event['id'],'kind':event['type']}}
            inserted=repo.record(observation)
            if inserted and hasattr(repo,'record_overhead'):repo.record_overhead(run,time.perf_counter_ns()-trace_started)
            result['trace_id']=observation['id']
    except Exception as exc:
        # Visible, bounded, payload-free diagnostics; no retry storm on a tool path.
        result['observability_error']=type(exc).__name__


def publish_component(home,config,identity,kind,attributes,*,start_ns,end_ns,event_id=None,source=None):
    if not enabled(config):return
    if not source and kind.startswith('learning.') and attributes.get('proposal_id'):
        source={'source_id':'gw-learning','proposal_id':attributes['proposal_id']}
    if not source and kind.startswith('sync.') and attributes.get('journal_id'):
        source={'source_id':'gw-sync','journal_id':attributes['journal_id']}
    try:
        with trace_repository(home,config) as repo:
            sid=identity.get('session_id') or digest([identity.get('client','generic'),identity['project'],identity.get('session','component')])
            run=repo.bind_session(sid,identity['project'],identity.get('client','generic'),run_id=identity.get('run_id') or os.environ.get('GW_RUN_ID'),config=config)
            repo.record({'protocol':'gw.observation/1','id':event_id or digest([kind,sid,start_ns]),'run_id':run,'session_id':sid,
                'parent_id':identity.get('parent_id'),'kind':kind,'start_ns':start_ns,'end_ns':end_ns,
                'attributes':attributes,'source':source or {}})
    except Exception as exc:
        # Component observability must not change tool/model output.
        import warnings
        warnings.warn('GW observation not recorded: '+type(exc).__name__,RuntimeWarning)
