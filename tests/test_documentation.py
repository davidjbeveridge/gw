"""Offline documentation checks: local links, snippets, policies and runnable examples.

These are not external-link checks, live-agent coverage, or model benchmarks.
The Markdown subset checked here is deliberate and dependency-free.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import unittest
import urllib.parse
from gw_supervisor.config import DEFAULTS, merge, validate
from gw_supervisor.proxy import WIRES
from gw_supervisor.util import strict_json

ROOT = pathlib.Path(__file__).resolve().parents[1]
LINK = re.compile(r'\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')


def documents():
    roots = [ROOT, ROOT / "docs", ROOT / "examples", ROOT / "packages/gw-knowledge", ROOT / "packages/gw-context", ROOT / "skills"]
    paths = set()
    for root in roots:
        paths.update(root.glob("*.md") if root == ROOT else root.rglob("*.md"))
    paths.add(ROOT / "llms.txt")
    return sorted(paths)


def parts(content):
    """Return prose and fenced blocks, ignoring Markdown-like code contents."""
    prose, blocks, current, language, fence = [], [], [], "", None
    for line in content.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is None and match:
            fence, language, current = match.group(1), match.group(2).strip(), []
        elif fence and match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
            blocks.append((language, "\n".join(current)))
            fence = None
        elif fence:
            current.append(line)
        else:
            prose.append(line)
    if fence:
        raise AssertionError("Unclosed fenced code block")
    return "\n".join(prose), blocks


def anchors(prose):
    found, counts = set(), {}
    for line in prose.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if not match:
            continue
        value = re.sub(r"<[^>]+>", "", match.group(1)).lower()
        value = re.sub(r"[^\w\- ]", "", value).replace(" ", "-")
        number = counts.get(value, 0)
        counts[value] = number + 1
        found.add(value if number == 0 else f"{value}-{number}")
    found.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', prose))
    return found


class DocumentationTests(unittest.TestCase):
    def test_local_links_and_heading_anchors_resolve(self):
        errors = []
        for path in documents():
            prose, _ = parts(path.read_text(encoding="utf-8"))
            for href in LINK.findall(prose):
                href = href.strip("<>")
                url = urllib.parse.urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / urllib.parse.unquote(url.path)).resolve() if url.path else path
                if not target.exists():
                    errors.append(f"{path.relative_to(ROOT)} -> missing {href}")
                elif url.fragment and target.suffix in {".md", ".txt"}:
                    target_prose, _ = parts(target.read_text(encoding="utf-8"))
                    if urllib.parse.unquote(url.fragment) not in anchors(target_prose):
                        errors.append(f"{path.relative_to(ROOT)} -> missing anchor {href}")
        self.assertEqual(errors, [])

    def test_json_fences_are_parseable_and_finite(self):
        for path in documents():
            _, blocks = parts(path.read_text(encoding="utf-8"))
            for language, content in blocks:
                if language == "json":
                    with self.subTest(path=str(path.relative_to(ROOT)), snippet=content[:60]):
                        strict_json(content)

    def test_python_fences_compile(self):
        for path in documents():
            _, blocks = parts(path.read_text(encoding="utf-8"))
            for language, content in blocks:
                if language in {"python", "py"}:
                    with self.subTest(path=str(path.relative_to(ROOT))):
                        compile(content, str(path), "exec")

    def test_example_policies_validate_without_mutating_defaults(self):
        before = json.dumps(DEFAULTS, sort_keys=True)
        for path in (ROOT / "examples/policies").glob("*.json"):
            with self.subTest(path=path.name):
                validate(merge(DEFAULTS, strict_json(path.read_text(encoding="utf-8"))))
        self.assertEqual(json.dumps(DEFAULTS, sort_keys=True), before)

    def test_documented_wire_contracts_match_implementation(self):
        prose = (ROOT / "docs/PROXY.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| ([^|]+) \|$", prose, re.MULTILINE)
        documented = {wire: (operation, modalities.strip()) for wire, operation, modalities in rows}
        self.assertEqual(set(documented), set(WIRES))
        for wire, (operation, inputs, outputs) in WIRES.items():
            with self.subTest(wire=wire):
                self.assertEqual(documented[wire], (operation, ",".join(inputs) + " → " + ",".join(outputs)))

    def test_quick_install_and_fork_are_at_the_top(self):
        opening = "\n".join((ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:20])
        self.assertIn("install.sh | bash -s -- --all", opening)
        self.assertIn("/gw/fork", opening)
        self.assertIn("Star", opening)

    def run_example(self, filename):
        run = subprocess.run([sys.executable, str(ROOT / "examples" / filename)], cwd=ROOT,
                             capture_output=True, text=True, timeout=20, check=True)
        return json.loads(run.stdout)

    def test_offline_supervision_example(self):
        result = self.run_example("supervision_demo.py")
        self.assertEqual(result, {"canary": "deny", "duplicate": True, "retry": "approve", "events": 5})

    @unittest.skipUnless(importlib.util.find_spec("gw_knowledge"), "Optional knowledge package not installed")
    def test_offline_knowledge_example(self):
        result = self.run_example("knowledge_demo.py")
        self.assertEqual(result, {"first_hit": False, "second_hit": True, "after_addition_hit": False,
                                 "documents": ["architecture", "operations"], "source_survives_eviction": True})


if __name__ == "__main__":
    unittest.main()
