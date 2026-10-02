"""Actual MCP SDK/client roundtrip; installed explicitly in the transport CI job."""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from gw_knowledge import LocalKnowledgeProvider, Scope, DocumentInput


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Install gw-knowledge[mcp] to exercise the real MCP transport')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_discovery_search_read_and_context(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as tmp:
            with LocalKnowledgeProvider(tmp) as provider:
                provider.put(Scope('local','demo','owner'),DocumentInput('doc','Title','needle evidence','file:///fixture'))
            params=StdioServerParameters(command=sys.executable,args=['-m','gw_knowledge','--store',tmp,'--collection','demo','mcp'],env=dict(os.environ))
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    tools=await session.list_tools()
                    names={tool.name for tool in tools.tools}
                    self.assertEqual(names,{'knowledge_search','knowledge_read','knowledge_context'})
                    for tool in tools.tools:
                        self.assertNotIn('scope',tool.inputSchema.get('properties',{}))
                        self.assertNotIn('principal',tool.inputSchema.get('properties',{}))
                    def obj(result):
                        self.assertFalse(result.isError)
                        return result.structuredContent or json.loads(result.content[0].text)
                    result=obj(await session.call_tool('knowledge_search',{'query':'needle'}))
                    hit=result['hits'][0]
                    read_result=obj(await session.call_tool('knowledge_read',{'document_id':'doc','revision':hit['revision']}))
                    self.assertEqual(read_result['text'],'needle evidence')
                    context=obj(await session.call_tool('knowledge_context',{'query':'needle'}))
                    self.assertEqual(context['evidence'][0]['revision'],hit['revision'])
                    resource=await session.read_resource(f"knowledge://documents/doc/{hit['revision']}")
                    self.assertEqual(json.loads(resource.contents[0].text)['text'],'needle evidence')

    async def test_writable_transport_explicitly_exposes_store(self):
        from gw_knowledge.mcp import build_server
        from gw_knowledge.service import KnowledgeService
        with tempfile.TemporaryDirectory() as tmp:
            with LocalKnowledgeProvider(tmp) as provider:
                server=build_server(KnowledgeService(provider,scope=Scope('local','demo','owner'),writable=True))
                tools=await server.list_tools()
                self.assertIn('knowledge_store',{tool.name for tool in tools})
