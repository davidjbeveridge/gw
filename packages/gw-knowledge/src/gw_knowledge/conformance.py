"""Read-only adapter smoke usable by third-party implementers; no fixture writes."""
from .contract import (
    SearchRequest, ReadRequest, validate_capabilities, validate_revision,
    validate_search, validate_passage, Unsupported, InvalidRequest,
)


def check_provider(provider, scope, query: str = "conformance") -> dict:
    """Validate required shapes and exact read-through for this authorized scope.

    Passing does not certify retrieval accuracy, ACL design or backend uptime.
    Use the packaged tests as the seeded reference conformance suite.
    """
    caps = validate_capabilities(provider.capabilities())
    before = validate_revision(provider.revision(scope))
    if caps["revision_tracking"] and before is None:
        raise InvalidRequest("Revision capability not implemented")
    mode = "keyword" if "keyword" in caps["search_modes"] else caps["search_modes"][0]
    request = SearchRequest(scope, "" if mode == "structured" else query, mode, limit=2)
    result = validate_search(provider.search(request), request)
    for hit in result["hits"]:
        read = validate_passage(provider.read(ReadRequest(scope, hit["document_id"], hit["revision"], hit["start_char"], hit["end_char"])), scope)
        if read["text"] != hit["text"] or read["revision"] != hit["revision"]:
            raise InvalidRequest("Search/read contract mismatch")
    return {"ok": True, "protocol": caps["protocol"], "provider_id": caps["provider_id"],
            "checked_reads": len(result["hits"]), "scope": scope.to_dict(),
            "accuracy_or_security_audit": False}


class ReadConformanceMixin:
    """Reusable unittest mixin for adapter authors.

    setUp must provide self.provider, self.scope, self.fixture_query and
    self.fixture_document_id, and seed a visible text document via trusted setup.
    The mixin itself never writes. Extend unittest.TestCase alongside this class.
    """
    def test_contract_capabilities(self):
        self.assertEqual(validate_capabilities(self.provider.capabilities())["protocol"], "gw.knowledge/1")

    def test_contract_search_read(self):
        result = check_provider(self.provider, self.scope, self.fixture_query)
        self.assertTrue(result["ok"])
        self.assertGreater(result["checked_reads"], 0)

    def test_contract_revision(self):
        token = validate_revision(self.provider.revision(self.scope))
        if self.provider.capabilities()["revision_tracking"]:
            self.assertIsNotNone(token)

    def test_contract_exact_range(self):
        full = validate_passage(self.provider.read(ReadRequest(self.scope, self.fixture_document_id)), self.scope)
        part = self.provider.read(ReadRequest(self.scope, self.fixture_document_id, full["revision"], 0, min(4, len(full["text"]))))
        self.assertEqual(part["text"], full["text"][:4])
        self.assertEqual(part["revision"], full["revision"])
