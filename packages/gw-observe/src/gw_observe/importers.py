"""Explicit, bounded transcript indexing. Raw lines remain in the original file.

Schemas are best-effort adapters, not universal agent formats. Unknown records
and reset counters are reported. Never sum repeated cumulative token counters.
"""
from __future__ import annotations
import datetime as dt
import json
import pathlib
import time
from .contract import PROTOCOL, canonical, digest, normalize_usage


def stamp(value,fallback):
    if not isinstance(value,str):return fallback
    try:
        parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:return fallback
        return int(parsed.timestamp()*1e9)
    except (ValueError,OverflowError):return fallback


def import_transcript(repo,run_id,path,format,*,session_id=None):
    if format not in {'claude-jsonl','codex-jsonl'}:raise ValueError('Supported transcripts: claude-jsonl, codex-jsonl')
    run=repo.run(run_id);p=pathlib.Path(path).expanduser().resolve()
    if not p.is_file() or p.stat().st_size>256*1024*1024:raise ValueError('Expected a transcript no larger than 256 MiB')
    source=repo.register_source(p,format)
    records={};counts={'lines':0,'unsupported':0,'invalid':0,'counter_resets':0,'duplicate_counters':0}
    native=session_id;model=run['manifest'].get('model');prior=None;fallback=run['started_ns']; offset=0
    def add(local,kind,attrs,ref,at,parent=None):
        client='claude' if format=='claude-jsonl' else 'codex'
        sid=digest([client,run['project'],native or source])
        eid=digest([format,native or source,local])
        records[eid]={'protocol':PROTOCOL,'id':eid,'run_id':run_id,'session_id':sid,
                      'parent_id':digest([format,native or source,parent]) if parent else None,
                      'kind':kind,'start_ns':at,'end_ns':at,'attributes':attrs,'source':ref}
    with p.open('rb') as stream:
        while True:
            data=stream.readline(1_048_577)
            if not data:break
            if len(data)>1_048_576:raise ValueError('Transcript line exceeds 1 MiB')
            counts['lines']+=1
            if counts['lines']>200000:raise ValueError('Transcript record budget exceeded')
            ref={'source_id':source,'offset':offset,'length':len(data),'hash':digest(data.hex())};offset+=len(data)
            try:raw=json.loads(data.decode())
            except (ValueError,UnicodeError):counts['invalid']+=1;continue
            if not isinstance(raw,dict):counts['invalid']+=1;continue
            at=stamp(raw.get('timestamp'),fallback);kind=raw.get('type');payload=raw.get('payload') or {}
            if not isinstance(payload,dict):payload={}
            if format=='claude-jsonl':
                native=session_id or raw.get('sessionId') or native
                message=raw.get('message') or {}
                if not isinstance(message,dict):counts['invalid']+=1;continue
                parent=raw.get('parentUuid')
                if kind=='assistant':
                    mid=message.get('id') or raw.get('uuid')
                    if not mid:counts['invalid']+=1;continue
                    model=message.get('model') or model
                    u=normalize_usage(message.get('usage',{}),'anthropic')
                    add('usage:'+mid,'model.usage',{'model':model,'request_id':mid,'usage':u,'usage_source':format,'billing_kind':'unknown'},ref,at)
                    add('turn:'+mid,'agent.turn',{'model':model,'turn_id':mid,'source_lane':format},ref,at)
                    for block in message.get('content',[]):
                        if isinstance(block,dict) and block.get('type')=='tool_use':
                            tid=block.get('id') or digest(block);name=block.get('name','unknown')
                            add('tool:'+tid,'agent.tool',{'tool':name,'tool_call_id':tid,'tool_class':classify(name),'tool_class_basis':'name_hint','source_lane':format},ref,at,'turn:'+mid)
                elif kind=='user':
                    content=message.get('content',[])
                    if isinstance(content,list) and content and all(isinstance(x,dict) and x.get('type')=='tool_result' for x in content):
                        for b in content:
                            tid=b.get('tool_use_id');add('result:'+str(tid),'agent.tool_result',{'tool_call_id':tid,'success':not b.get('is_error',False),'source_lane':format},ref,at,'tool:'+str(tid))
                    else:add('user:'+str(raw.get('uuid') or ref['offset']),'agent.user_turn',{'turn_id':raw.get('uuid') or str(ref['offset']),'source_lane':format},ref,at)
                else:counts['unsupported']+=1
            else:
                if kind=='session_meta':native=session_id or payload.get('id') or native
                elif kind=='turn_context':model=payload.get('model') or model
                elif kind=='event_msg' and payload.get('type')=='token_count':
                    info=payload.get('info') or {};current=info.get('total_token_usage') if isinstance(info,dict) else None
                    if not isinstance(current,dict):counts['invalid']+=1;continue
                    totals=normalize_usage(current)
                    if prior is not None and any(totals.get(k,0)<v for k,v in prior.items()):
                        counts['counter_resets']+=1;prior=totals;continue
                    delta={k:v-(prior or {}).get(k,0) for k,v in totals.items()}
                    if prior is not None and not any(delta.values()):counts['duplicate_counters']+=1;continue
                    prior=totals
                    add('usage:'+str(ref['offset']),'model.usage',{'model':model,'usage':delta,'usage_source':format,
                        'measurement':'delta_of_reported_session_cumulative_counters','billing_kind':'unknown'},ref,at)
                elif kind=='event_msg' and payload.get('type')=='user_message':
                    add('user:'+str(ref['offset']),'agent.user_turn',{'turn_id':str(ref['offset']),'source_lane':format},ref,at)
                elif kind=='response_item' and payload.get('type') in {'function_call','custom_tool_call'}:
                    tid=payload.get('call_id') or str(ref['offset']);name=payload.get('name','unknown')
                    add('tool:'+tid,'agent.tool',{'tool':name,'tool_call_id':tid,'tool_class':classify(name),'tool_class_basis':'name_hint','source_lane':format},ref,at)
                elif kind=='response_item' and payload.get('type')=='message' and payload.get('role')=='assistant':
                    # Assistant messages are distinct from model calls; report their
                    # count separately rather than pretending token events are turns.
                    add('message:'+str(ref['offset']),'agent.assistant_message',{'model':model,'source_lane':format},ref,at)
                else:counts['unsupported']+=1
    added=0;updated=0
    for event in records.values():
        old=repo.db.execute('SELECT attributes,source,run_id FROM observations WHERE id=?',(event['id'],)).fetchone()
        if old:
            if old['run_id']!=run_id:raise ValueError('Transcript event already belongs to another run')
            original=json.loads(old[0]);original.pop('previous_source_hash',None)
            if canonical(original)!=canonical(event['attributes']) or old[1]!=canonical(event['source']):
                # Streaming transcripts can revise usage on the same message ID.
                # Keep one canonical measurement plus prior locator/hash, not a
                # second counted model call.
                event['attributes']['previous_source_hash']=digest(json.loads(old[1]))
                with repo.db:repo.db.execute('UPDATE observations SET attributes=?,source=?,end_ns=? WHERE id=? AND run_id=?',
                    (canonical(event['attributes']),canonical(event['source']),event['end_ns'],event['id'],run_id))
                updated+=1
        else:added+=repo.record(event)
    return {**counts,'inserted':added,'revised':updated,'source_id':source,'raw_content_copied':False,
        'coverage':'recognized records only; local session schemas may change','token_cost':'not estimated'}


def classify(name):
    n=str(name).lower()
    if any(x in n for x in ('computer','mouse','desktop')):return 'computer_use'
    if any(x in n for x in ('browser','chrome','playwright')):return 'browser'
    if n.startswith('mcp'):return 'mcp'
    if n in {'bash','shell','powershell','exec_command','run_command','terminal'}:return 'cli'
    if n in {'read','write','edit','apply_patch','glob','grep'}:return 'native'
    return 'unknown'
