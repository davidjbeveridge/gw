import tempfile
import unittest
from unittest import mock
from gw_knowledge import Scope, LocalKnowledgeProvider
from gw_knowledge.http import make_server
from gw_knowledge.service import KnowledgeService


class ServerStartupTests(unittest.TestCase):
    def test_literal_loopback_startup_does_not_use_dns(self):
        with tempfile.TemporaryDirectory() as tmp:
            with LocalKnowledgeProvider(tmp) as provider:
                service = KnowledgeService(provider, scope=Scope("local", "test", "owner"))
                with mock.patch("socket.getfqdn", side_effect=AssertionError("No DNS for loopback")):
                    server = make_server(service, "a-private-test-token-at-least-20-characters")
                    try:
                        self.assertEqual(server.server_name, "127.0.0.1")
                        self.assertGreater(server.server_port, 0)
                    finally:
                        server.server_close()
