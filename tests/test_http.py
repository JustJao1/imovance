import unittest, tempfile, threading, urllib.request, urllib.error, json, http.cookiejar, uuid, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class HTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); app.DB=str(Path(self.tmp.name)/'http.sqlite'); app.init()
        self.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler); self.origin='http://127.0.0.1:'+str(self.server.server_port); app.ORIGIN=self.origin
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); self.a=self.client(); self.b=self.client()
    def tearDown(self): self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def client(self): return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,c,route,body=None,key=None,origin=None):
        headers={'Content-Type':'application/json','Origin':origin or self.origin,'Idempotency-Key':key or str(uuid.uuid4())}; req=urllib.request.Request(self.origin+'/api/'+route,None if body is None else json.dumps(body).encode(),headers)
        try:
            with c.open(req,timeout=4) as r: return r.status,json.loads(r.read())
        except urllib.error.HTTPError as r: return r.code,json.loads(r.read())
    def register(self,c,email):
        self.assertEqual(self.request(c,'register',{'email':email,'name':'Teste','organization':email,'password':'senha-local-123456'})[0],200)
    def test_api(self):
        self.assertEqual(self.request(self.a,'state')[0],401); self.register(self.a,'a@example.com'); self.register(self.b,'b@example.com'); key=str(uuid.uuid4()); data={'name':'Apartamento 102'}
        status,p=self.request(self.a,'properties',data,key); self.assertEqual(status,200); self.assertEqual(self.request(self.a,'properties',data,key),(200,p)); self.assertEqual(self.request(self.a,'properties',{'name':'Outro'},key)[0],400)
        self.assertEqual(len(self.request(self.a,'state')[1]['properties']),1); self.assertEqual(self.request(self.b,'state')[1]['properties'],[])
        self.assertEqual(self.request(self.b,'properties',{'id':p['id'],'name':'Invasão'})[0],404); self.assertEqual(self.request(self.a,'properties',{'name':'Inválido'},origin='http://example.com')[0],400)
        self.assertEqual(self.request(self.a,'logout',{})[0],200); self.assertEqual(self.request(self.a,'state')[0],401); self.assertEqual(self.request(self.a,'login',{'email':'a@example.com','password':'senha-local-123456'})[0],200); self.assertEqual(len(self.request(self.a,'state')[1]['properties']),1)
    def test_operations_api(self):
        self.register(self.a,'ops-a@example.com'); self.register(self.b,'ops-b@example.com')
        _,prop=self.request(self.a,'properties',{'name':'Apartamento'}); pid=prop['id']
        booking={'property_id':pid,'guest':'Teste','arrival':'2027-01-01','departure':'2027-01-05'}
        self.assertEqual(self.request(self.a,'reservations/save',booking)[0],200)
        self.assertEqual(self.request(self.a,'reservations/save',booking)[0],400)
        self.assertEqual(self.request(self.b,'reservations/save',booking)[0],404)
        _,r=self.request(self.a,'receivables/save',{'property_id':pid,'title':'Aluguel','payer':'Teste','amount':15500,'due':app.today()})
        self.assertEqual(self.request(self.b,'receivables/status',{'id':r['id'],'status':'Recebida'})[0],404)
        key=str(uuid.uuid4());body={'id':r['id'],'status':'Recebida','date':app.today()}
        first=self.request(self.a,'receivables/status',body,key);self.assertEqual(first[0],200);self.assertEqual(self.request(self.a,'receivables/status',body,key),first)
        self.assertEqual(self.request(self.a,'receivables/status',body)[0],400)
        state=self.request(self.a,'state')[1];self.assertEqual(len(state['finance']),1);self.assertEqual(state['finance'][0]['amount'],15500);self.assertEqual(len(state['reservations']),1)
        other=self.request(self.b,'state')[1];self.assertEqual(other['reservations'],[]);self.assertEqual(other['receivables'],[])
if __name__=='__main__': unittest.main()
