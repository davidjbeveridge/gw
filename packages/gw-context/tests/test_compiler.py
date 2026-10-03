import unittest
from gw_context.compiler import ContextItem, DeterministicContextCompiler, ContextBudgetExceeded
from gw_context.contract import InvalidRequest, canonical

class CompilerTests(unittest.TestCase):
    def item(self, id='source', content='Use a fixture database.', **kw):
        return ContextItem(id, 'project', content, 'project:'+id, 'revision-1', **kw)
    def test_required_atomic_and_provenance(self):
        skill = self.item('skill', 'Never submit before review.\nUse the exact fixture.', required=True)
        result = DeterministicContextCompiler().compile('Fill a form', [skill], max_chars=1000)
        self.assertEqual(result['payload']['items'][0]['content'], skill.content)
        self.assertEqual(result['selected'][0]['end_char'], len(skill.content))
        self.assertEqual(result['model_calls'], 0)
    def test_required_does_not_fit_fails_instead_of_truncating(self):
        with self.assertRaises(ContextBudgetExceeded):
            DeterministicContextCompiler().compile('Task', [self.item(content='a'*2000, required=True)], max_chars=512)
    def test_optional_budget_and_stable_order(self):
        items=[self.item('z', 'unrelated '*50), self.item('a', 'fixture '*20)]
        compiler=DeterministicContextCompiler()
        a=compiler.compile('fixture', items, max_chars=700)
        b=compiler.compile('fixture', list(reversed(items)), max_chars=700)
        self.assertEqual(a['text'], b['text']); self.assertLessEqual(a['compiled_chars'],700)
        self.assertTrue(a['omitted']); self.assertEqual(a['selected'][0]['id'],'a')
    def test_duplicate_required_wins(self):
        a=self.item(); b=ContextItem('required','skill',a.content,a.source,a.revision,True)
        result=DeterministicContextCompiler().compile('Task',[a,b])
        self.assertEqual(len(result['selected']),1); self.assertTrue(result['selected'][0]['required'])
        self.assertEqual(result['omitted'][0]['reason'],'duplicate')
    def test_conflicting_revisions_rejected(self):
        a=self.item(); b=ContextItem('b','project','new',a.source,'revision-2')
        with self.assertRaises(InvalidRequest): DeterministicContextCompiler().compile('Task',[a,b])
    def test_changed_source_changes_packet_identity(self):
        compiler=DeterministicContextCompiler()
        self.assertNotEqual(compiler.compile('Task',[self.item()])['id'], compiler.compile('Task',[self.item(content='changed')])['id'])
    def test_unicode_budget_matches_actual_payload(self):
        result=DeterministicContextCompiler().compile('任务',[self.item(content='🐱\r\nnaïve')])
        self.assertEqual(result['compiled_chars'],len(canonical(result['payload'])))
    def test_invalid_input_and_budget(self):
        for budget in (True, 0, 999999):
            with self.assertRaises(InvalidRequest): DeterministicContextCompiler().compile('Task',[],max_chars=budget)
        with self.assertRaises(InvalidRequest): DeterministicContextCompiler().compile('Task',[{}])
