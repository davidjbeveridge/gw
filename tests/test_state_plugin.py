"""The reference repository atomically persists canonical events and extension state."""
import pathlib
import tempfile
import unittest
from gw_supervisor.api import canonical
from gw_supervisor.engine import Supervisor

class StatePluginTests(unittest.TestCase):
    def test_commit_rollback_and_latest_namespaced_state(self):
        with tempfile.TemporaryDirectory() as tmp, Supervisor(pathlib.Path(tmp)/'state') as runtime:
            event={'client':'generic','project':tmp,'session':'s','id':'one','type':'tool.before','tool':'Read'}
            session=runtime.session_context(event);store=runtime.store
            with self.assertRaises(TypeError):store.commit(session,event,{'decision':'allow'},{'extension':{'bad':object()}})
            self.assertIsNone(store.cached_event(session['id'],event))
            store.commit(session,event,{'decision':'deny'},{'extension':{'n':1}})
            store.commit(session,event,{'decision':'allow'},{'extension':{'n':2}})
            self.assertEqual(store.read_state(session['id'],'extension'),{'n':1})
            store.commit(session,{**event,'id':'two'},{'decision':'allow'},{'extension':{'n':3}})
            self.assertEqual(store.read_state(session['id'],'extension'),{'n':3})
            self.assertEqual(store.cached_event(session['id'],event)['decision'],'deny')
