import base64
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('ocr_server', ROOT / 'server/ocr_server.py')
ocr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr)
IMAGE = 'data:image/png;base64,' + base64.b64encode(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZqkAAAAASUVORK5CYII=')).decode()


class Upstream(BaseHTTPRequestHandler):
    calls = []
    content = json.dumps({'candidates': [{'character': '峯', 'reason': '保留原字形'}], 'note': '人工核对'})
    def log_message(self,*args):
        pass
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append((self.path,self.headers['Authorization'],payload))
        if self.path.startswith('/redirect/'):
            self.send_response(302)
            self.send_header('Location','/v1/chat/completions')
            self.end_headers()
            return
        if self.path.startswith('/error/'):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'private provider error with credential-test-fixture')
            return
        raw=json.dumps({'choices':[{'message':{'content':self.content}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class OCRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        cls.provider_thread=threading.Thread(target=cls.provider.serve_forever,daemon=True)
        cls.provider_thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.provider.shutdown();cls.provider.server_close();cls.provider_thread.join()
    def setUp(self):
        Upstream.calls=[]
        Upstream.content=json.dumps({'candidates':[{'character':'峯','reason':'保留原字形'}],'note':'人工核对'})
        self.config=ocr.load_config()
        self.config.update(enabled=True,base_url=f'http://127.0.0.1:{self.provider.server_port}/v1',api_key='credential-test-fixture',model='vision-test-fixture',requests_per_minute=120)
        self.server=ocr.OCRServer(('127.0.0.1',0),partial(ocr.Handler,directory=str(ROOT)),self.config)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path='/api/ocr',body=None,origin=None,headers=None):
        if body is None: body={'image':IMAGE}
        request=Request(self.base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':origin or self.base,**(headers or {})})
        try:
            with urlopen(request,timeout=5) as response:return response.status,response.read().decode()
        except HTTPError as error:return error.code,error.read().decode()
    def test_openai_multimodal_and_no_secrets_in_response(self):
        code,raw=self.request()
        self.assertEqual(code,200)
        self.assertEqual(json.loads(raw)['candidates'][0]['character'],'峯')
        path,auth,payload=Upstream.calls[0]
        self.assertEqual(path,'/v1/chat/completions')
        self.assertEqual(auth,'Bearer credential-test-fixture')
        self.assertEqual(payload['model'],'vision-test-fixture')
        self.assertEqual(payload['messages'][1]['content'][1]['image_url']['url'],IMAGE)
        self.assertNotIn('credential-test-fixture',raw)
    def test_disabled_status_and_no_provider_call(self):
        self.config['enabled']=False
        code,raw=self.request()
        self.assertEqual(code,503);self.assertFalse(Upstream.calls)
        with urlopen(self.base+'/api/ocr/status') as response:
            self.assertEqual(json.load(response),{'configured':False})
    def test_origin_and_image_validation(self):
        self.assertEqual(self.request(origin='https://untrusted.example')[0],403)
        self.assertEqual(self.request(body={'image':'https://untrusted.example/a.png'})[0],400)
        self.assertEqual(self.request(body={'image':'data:image/png;base64,YmFk'})[0],400)
        self.assertEqual(self.request(headers={'Content-Type':'text/plain'})[0],415)
        self.assertFalse(Upstream.calls)
    def test_provider_errors_are_sanitized_and_redirect_not_followed(self):
        for segment in ['error','redirect']:
            self.config['base_url']=f'http://127.0.0.1:{self.provider.server_port}/{segment}'
            code,raw=self.request()
            self.assertEqual(code,502)
            self.assertNotIn('credential-test-fixture',raw)
        self.assertEqual(len(Upstream.calls),2)
    def test_bad_model_output_and_empty_candidates(self):
        for content in ['not-json','{"candidates":[{"character":"峰山"}]}','{"candidates":[{"character":"<"}]}']:
            Upstream.content=content
            self.assertEqual(self.request()[0],502)
        Upstream.content='{"candidates":[],"note":"模糊"}'
        code,raw=self.request();self.assertEqual(code,200);self.assertEqual(json.loads(raw)['candidates'],[])
    def test_rate_limit(self):
        self.config['requests_per_minute']=1
        self.assertEqual(self.request()[0],200)
        self.assertEqual(self.request()[0],429)
        self.assertEqual(len(Upstream.calls),1)
    def test_private_files_not_served(self):
        for path in ['/server/ocr-config.example.json','/.git/config','/scripts/deploy-artifact.sh','/assets/../server/ocr_server.py','/assets/']:
            try:
                urlopen(self.base+path,timeout=5)
                self.fail(path+' exposed')
            except HTTPError as error:self.assertEqual(error.code,404,path)
        with urlopen(self.base+'/assets/variant-core.js') as response:self.assertEqual(response.status,200)
    def test_config_cannot_live_in_webroot(self):
        with self.assertRaises(ValueError):ocr.load_config(ROOT/'server/ocr-config.example.json')
    def test_candidate_dedup_and_supplementary_codepoint(self):
        result=ocr.parse_candidates('{"candidates":[{"character":"𠮷"},{"character":"𠮷"}]}')
        self.assertEqual(len(result['candidates']),1)
        self.assertEqual(result['candidates'][0]['character'],'𠮷')


if __name__=='__main__':unittest.main()
