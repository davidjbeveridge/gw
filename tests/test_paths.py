"""Regression for path aliases causing silently unpinned tasks on macOS/Windows."""
import pathlib
import tempfile
import unittest
from gw_supervisor.engine import Supervisor


class PathTests(unittest.TestCase):
    def test_task_canonicalization_at_storage_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            project = root / 'project'
            child = project / 'child'
            child.mkdir(parents=True)
            (project / '.git').mkdir()
            alias = str(child / '..')
            with Supervisor(root / 'state') as supervisor:
                supervisor.store.set_task(alias, 'Pinned task')
                event = {'type': 'tool.before', 'project': str(project.resolve()), 'session': 's', 'client': 'custom', 'tool': 'Read', 'input': {}}
                self.assertEqual(supervisor.session_context(event)['task'], 'Pinned task')


if __name__ == '__main__':
    unittest.main()
