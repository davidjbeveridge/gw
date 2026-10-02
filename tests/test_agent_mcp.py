"""Actual SDK/stdio test. CI installs the optional agent extra explicitly."""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional MCP SDK not installed')
class AgentMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_operates_setup_and_context_without_user_commands(self):
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp).resolve();project=root/'project';project.mkdir()
            (project/'README.md').write_text('Login validation requires fixture tests.')
            params=StdioServerParameters(command=sys.executable,args=['-m','gw_supervisor','--home',str(root/'state'),'agent','serve','--project',str(project),'--client','codex','--manage'],env=dict(os.environ))
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as client:
                    await client.initialize()
                    tools=await client.list_tools();names={t.name for t in tools.tools}
                    self.assertTrue({'gw_status','gw_configure_plan','gw_configure_apply','gw_context_compile','gw_dashboard_open'}<=names)
                    for tool in tools.tools:self.assertNotIn('project',tool.inputSchema.get('properties',{}))
                    def obj(result):
                        self.assertFalse(result.isError,str(result))
                        return result.structuredContent or json.loads(result.content[0].text)
                    status=obj(await client.call_tool('gw_status',{}));self.assertEqual(status['project'],str(project))
                    plan=obj(await client.call_tool('gw_configure_plan',{'patch':{'context_compiler':{'enabled':True,'knowledge':False}}}))
                    applied=obj(await client.call_tool('gw_configure_apply',{'plan_id':plan['id']}));self.assertTrue(applied['applied'])
                    packet=obj(await client.call_tool('gw_context_compile',{'task':'Fix login validation','query':'fixture'}))
                    self.assertEqual(packet['model_calls'],0);self.assertTrue(packet['selected'])
                    prompts=await client.list_prompts();self.assertIn('gw',{p.name for p in prompts.prompts})
                    resources=await client.read_resource('gw://status');self.assertEqual(json.loads(resources.contents[0].text)['client'],'codex')
    async def test_readonly_surface_omits_management_tools(self):
        from gw_supervisor.agent import AgentService,build_server
        with tempfile.TemporaryDirectory() as tmp:
            server=build_server(AgentService(pathlib.Path(tmp)/'state',tmp))
            names={t.name for t in await server.list_tools()}
            self.assertIn('gw_context_compile',names);self.assertIn('gw_trace_query',names)
            self.assertNotIn('gw_configure_apply',names);self.assertNotIn('gw_configure_plan',names)
            self.assertNotIn('gw_dashboard_open',names)
