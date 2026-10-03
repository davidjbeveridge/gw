"""External governance adapter. Unsupported obligations fail closed."""
import os
from gw_supervisor.api import Assessment, Advice, post_json, redact

class HttpAuthority:
    def __init__(self, config: dict):
        self.config = config

    def authorize(self, request: dict) -> dict:
        c = self.config
        result = post_json(c["endpoint"], {"version": 1, **redact(request)}, os.environ.get(c.get("key_env", "GW_AUTHORITY_TOKEN"), ""), min(c.get("timeout_seconds", 2), 5))
        if result.get("decision") not in {"allow", "deny", "approve"}:
            raise ValueError("Authority returned an invalid decision")
        # Never claim to enforce obligations this executor doesn't understand.
        if result.get("constraints") or result.get("obligations"):
            return {"decision": "deny", "reason": "Authority returned unsupported constraints; an executor integration is required"}
        return {"decision": result["decision"], "reason": str(redact(result.get("reason", "External authority")))[:1000], "receipt": redact(result.get("receipt"))}


def baseline(ctx):
    if ctx.config.get('authority', {}).get('endpoint') or ctx.overrides.get('authority'):
        raise ValueError('Baseline cannot bypass a configured or injected authority')
    return {}


def assess(ctx):
    c = ctx.config.get('authority', {})
    if ctx.event['type'] not in {'tool.before', 'model.request', 'inference.select'} or not (c.get('endpoint') or ctx.overrides.get('authority')):
        return Assessment()
    try:
        provider = ctx.overrides.get('authority') or HttpAuthority(c)
        result = provider.authorize({'session': ctx.session['id'], 'task': ctx.session['task'],
            'policy_hash': ctx.result['policy_hash'], 'event': redact(ctx.event),
            'inference_plan': ctx.result.get('inference', {}).get('plan')})
        if result.get('decision') not in {'allow', 'approve', 'deny'}:
            raise ValueError('Invalid authority decision')
        return Assessment((Advice(result['decision'], result.get('reason', 'External authority')),), {'authority': redact(result)})
    except Exception as exc:
        return Assessment((Advice('deny', 'Authority unavailable (' + type(exc).__name__ + '); refusing to proceed'),))
