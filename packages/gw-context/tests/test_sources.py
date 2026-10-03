"""Source contracts and boundaries require no GW or knowledge installation."""
import importlib.abc
import pathlib
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from gw_context import (
    ContextItem, ContextRequest, SourceResult, DeterministicContextCompiler,
    collect, open_source, installed_sources, InvalidRequest,
)
from gw_context.text import chunks


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.request = ContextRequest("Fix the bug", "host-scope", query="fixture", limit=2)
        self.item = ContextItem("doc", "knowledge", "Evidence", "vendor:doc", "v1")

    def result(self, **kw):
        return SourceResult(**{"items": (self.item,), "scope": self.request.scope, **kw})

    def test_third_party_source_without_storage(self):
        source = Mock()
        source.collect.return_value = self.result()
        result = collect(source, self.request, namespace="external")
        packet = DeterministicContextCompiler().compile(self.request.task, list(result.items), scope=result.scope)
        self.assertEqual(packet["model_calls"], 0)
        self.assertIsNone(result.revision)
        self.assertEqual(packet["payload"]["items"][0]["content"], "Evidence")
        source.collect.assert_called_once_with(self.request)

    def test_scope_mismatch_is_not_accepted(self):
        source = Mock()
        source.collect.return_value = self.result(scope="another-principal")
        with self.assertRaises(InvalidRequest):
            collect(source, self.request, namespace="external")

    def test_source_cannot_promote_itself_to_required_or_trusted(self):
        for item in (replace(self.item, required=True), replace(self.item, trust="host_instruction")):
            source = Mock()
            source.collect.return_value = self.result(items=(item,))
            with self.subTest(item=item), self.assertRaises(InvalidRequest):
                collect(source, self.request, namespace="external")

    def test_provider_namespaces_do_not_collide(self):
        source = Mock()
        source.collect.return_value = self.result()
        a = collect(source, self.request, namespace="a")
        b = collect(source, self.request, namespace="b")
        self.assertNotEqual(a.items[0].source, b.items[0].source)
        packet = DeterministicContextCompiler().compile("Task", [*a.items, *b.items])
        self.assertEqual(len(packet["selected"]), 2)

    def test_scope_changes_packet_identity(self):
        compiler = DeterministicContextCompiler()
        a = compiler.compile("Task", [self.item], scope="principal-a")
        b = compiler.compile("Task", [self.item], scope="principal-b")
        self.assertNotEqual(a["id"], b["id"])

    def test_item_and_result_limits(self):
        source = Mock()
        source.collect.return_value = self.result(items=(self.item,) * 3)
        with self.assertRaises(InvalidRequest):
            collect(source, self.request, namespace="external")
        for limit in (0, True, 257):
            with self.assertRaises(InvalidRequest):
                ContextRequest("Task", "scope", limit=limit)
        with self.assertRaises(InvalidRequest):
            SourceResult((replace(self.item, content="x" * 1_100_000),) * 2, "scope")

    def test_discovery_does_not_load_code(self):
        ep = Mock(name="factory")
        ep.name = "vendor"
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            self.assertEqual(installed_sources(), ["vendor"])
            ep.load.assert_not_called()

    def test_explicit_factory_and_no_duplicate_plugins(self):
        ep = Mock()
        source = Mock()
        ep.load.return_value.return_value = source
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            self.assertIs(open_source("vendor", {}), source)
        for entries in ([], [ep, ep]):
            with patch("importlib.metadata.entry_points", return_value=entries), self.assertRaises(InvalidRequest):
                open_source("vendor", {})

    def test_unicode_chunk_ranges_and_boundaries(self):
        content = "One 🐱\r\nSecond line\n終わり"
        parts = list(chunks(content, width=9))
        self.assertEqual("".join(p[1] for p in parts), content)
        for _, part, start, end, first, last in parts:
            self.assertEqual(content[start:end], part)
            self.assertGreaterEqual(first, 1)
            self.assertGreaterEqual(last, first)
        for width in (0, -1, True):
            with self.assertRaises(InvalidRequest):
                list(chunks(content, width))
        self.assertEqual(list(chunks("")), [(0, "", 0, 0, 1, 1)])

    def test_compilation_cannot_import_knowledge_or_harness(self):
        # A fresh interpreter prevents an earlier test's import cache from hiding
        # an accidental dependency, even in the all-packages integration matrix.
        code = '''
import importlib.abc, sys
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'gw_knowledge','gw_supervisor','sqlite3'}:
            raise AssertionError('Unexpected dependency: ' + fullname)
sys.meta_path.insert(0, Reject())
from gw_context import ContextItem, DeterministicContextCompiler
packet = DeterministicContextCompiler().compile('Task', [ContextItem('x','project','text','fixture','v1')])
assert packet['model_calls'] == 0 and packet['selected']
'''
        subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, timeout=20)
