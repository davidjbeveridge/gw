import importlib.resources
import importlib.util
import json
import tempfile
import unittest
from gw_knowledge import PROTOCOL,Scope,SearchRequest,DocumentInput,LocalKnowledgeProvider,ContextCache
from gw_knowledge.service import KnowledgeService


@unittest.skipUnless(importlib.util.find_spec('jsonschema'),'Optional contract-schema validator')
class SchemaTests(unittest.TestCase):
    def setUp(self):
        from jsonschema import Draft202012Validator
        self.schema=json.loads(importlib.resources.files('gw_knowledge').joinpath('schemas/contract-v1.json').read_text())
        Draft202012Validator.check_schema(self.schema)
        self.validator=Draft202012Validator(self.schema)
    def test_packaged_schema_matches_real_requests_and_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            with LocalKnowledgeProvider(tmp) as p,ContextCache(tmp+'/cache') as cache:
                scope=Scope('local','project','owner');s=KnowledgeService(p,cache,scope=scope,writable=True)
                d=DocumentInput('doc','Title','needle evidence','file:///test')
                commands=[('capabilities',{}),('put',{'scope':scope.to_dict(),'document':d.to_dict()}),('revision',{'scope':scope.to_dict()}),('search',{'scope':scope.to_dict(),'query':'needle'}),('read',{'scope':scope.to_dict(),'document_id':'doc'}),('context',{'scope':scope.to_dict(),'query':'needle'})]
                for method,request in commands:
                    envelope={'protocol':PROTOCOL,'method':method,'request':request}
                    with self.subTest(method=method):
                        self.validator.validate(envelope);self.validator.validate(s.handle(envelope))
                self.validator.validate(s.handle({'protocol':PROTOCOL,'method':'context','request':{'scope':scope.to_dict(),'query':'needle'}}))
    def test_wrong_protocol_and_extra_request_fields_are_invalid(self):
        self.assertFalse(self.validator.is_valid({'protocol':'wrong/1','method':'capabilities','request':{}}))
        self.assertFalse(self.validator.is_valid({'protocol':PROTOCOL,'method':'search','request':{'scope':Scope('a','b','c').to_dict(),'query':'x','admin':True}}))
