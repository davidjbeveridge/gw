"""Real HTTP + browser E2E; explicit optional CI job, not live agent coverage."""
import importlib.util
import json
import os
import pathlib
import tempfile
import threading
import unittest

@unittest.skipUnless(os.environ.get('GW_BROWSER_TEST')=='1' and importlib.util.find_spec('playwright'), 'Explicit browser job only')
class BrowserTests(unittest.TestCase):
    def test_local_dashboard_detail_comparison_and_mobile(self):
        from playwright.sync_api import sync_playwright
        from gw_observe.store import LocalTraceRepository
        from gw_observe.server import make_server
        with tempfile.TemporaryDirectory() as tmp:
            with LocalTraceRepository(tmp) as repo:
                for i in range(2):
                    run=repo.start('Synthetic fixture '+str(i),tmp,harness='fixture',model='model-'+str(i))
                    repo.record({'protocol':'gw.observation/1','id':'event-'+str(i),'run_id':run['id'],'kind':'model.usage',
                        'start_ns':run['started_ns'],'end_ns':run['started_ns']+100,'attributes':{'usage':{'input_tokens':10+i,'output_tokens':5},'usage_source':'declared','model':'fixture'},'source':{}})
            server=make_server(tmp);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as p:
                    options={'headless':True}
                    if os.environ.get('GW_CHROMIUM'):options['executable_path']=os.environ['GW_CHROMIUM']
                    browser=p.chromium.launch(**options);page=browser.new_page(viewport={'width':1440,'height':1000})
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/#token={server.token}')
                    page.locator('#title').filter(has_text='Synthetic fixture').wait_for()
                    self.assertIn('Unknown',page.locator('#metrics').inner_text())
                    page.get_by_role('button',name='Trace',exact=True).click();page.locator('#timeline button').first.click()
                    page.locator('dialog[open]').wait_for();self.assertIn('Recorded metadata',page.locator('#detail').inner_text())
                    page.get_by_role('button',name='Close event detail').click()
                    boxes=page.locator('#runs input[type=checkbox]');boxes.nth(0).check();boxes.nth(1).check();page.locator('#compare').click()
                    page.locator('#comparison h1').wait_for();self.assertIn('No causal',page.locator('#comparison').inner_text())
                    page.locator('#close-compare').click();page.set_viewport_size({'width':390,'height':844})
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth>window.innerWidth'))
                    self.assertEqual(errors,[]);browser.close()
            finally:server.shutdown();thread.join();server.server_close()
