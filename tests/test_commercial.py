import tempfile,unittest,sys,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,commercial
class Commercial(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DB=str(Path(self.tmp.name)/'test.db');app.init()
  with app.transaction() as c:
   self.u=c.execute("INSERT INTO users(email,name,password) VALUES('t@example.com','Teste','unused')").lastrowid
   self.o=c.execute("INSERT INTO organizations(name) VALUES('Teste')").lastrowid
   self.b=c.execute("INSERT INTO organizations(name) VALUES('Outra')").lastrowid
   c.execute('INSERT INTO memberships VALUES(?,?,?)',(self.u,self.o,'owner'))
  self.p=self.m('properties',{'name':'Apartamento'})['id']
 def tearDown(self):self.tmp.cleanup()
 def m(self,r,d):
  with app.transaction() as c:return app.mutate(c,self.o,self.u,r,d)
 def snap(self):
  with app.transaction() as c:return commercial.extend_snapshot(c,self.o,app.snapshot(c,self.o))
 def test_plan_limit(self):
  with self.assertRaises(app.Error):self.m('properties',{'name':'Segundo'})
  self.m('properties/archive',{'id':self.p,'archived':1});self.m('properties',{'name':'Segundo'})
  with self.assertRaises(app.Error):self.m('properties/archive',{'id':self.p,'archived':0})
 def test_stock_and_extra(self):
  i=self.m('items',dict(property_id=self.p,name='Garfos',room='Cozinha',category='Utensílios',needed=5,quantity=1,damaged=0))['id'];r=self.m('stock/save',dict(title='Garfos',category='Utensílios',quantity=4,minimum=1))['id'];self.m('stock/move',dict(id=r,target=i,quantity=4));s=self.snap();self.assertEqual(s['stock'][0]['quantity'],0);self.assertEqual(s['items'][0]['quantity'],5);self.assertEqual(s['issues'][0]['status'],'Aguardando conferência')
  rid=self.m('extra/save',dict(module='maintenance',record=dict(property_id=self.p,title='Torneira',status='Aberta'),expense=0))['id'];self.m('extra/issue',dict(module='maintenance',id=rid,title='Reparar',priority='Normal'));self.m('extra/save',dict(module='maintenance',id=rid,record=dict(property_id=self.p,title='Torneira',status='Concluída'),expense=15000));self.assertEqual(self.snap()['finance'][0]['amount'],15000)
  with self.assertRaises(app.Error):self.m('extra/save',dict(module='maintenance',id=rid,record=dict(property_id=self.p,title='Torneira',status='Concluída'),expense=15000))
  with app.transaction() as c:self.assertEqual(commercial.extend_snapshot(c,self.b,app.snapshot(c,self.b))['maintenance'],[])
 def test_billing_mock(self):
  def fake(path,data=None):
   if path.startswith('/customers?'):return {'data':[]}
   if path=='/customers':return {'id':'cus_test'}
   if path.startswith('/payments?'):return {'data':[]}
   if path=='/payments':return {'id':'pay_test','customer':'cus_test','value':39.90,'invoiceUrl':'https://sandbox.asaas.com/i/test'}
   if path=='/payments/pay_test':return {'id':'pay_test','value':39.90,'status':'RECEIVED'}
  with patch.dict(os.environ,{'ASAAS_API_KEY':'test-only'}),patch.object(commercial,'asaas',side_effect=fake):
   self.m('billing/checkout',{'plan':'essential','cpf':'12345678901'});self.assertEqual(self.snap()['billing']['plan'],'free');self.m('billing/refresh',{});self.assertEqual(self.snap()['billing']['limit'],5);self.m('properties',{'name':'Segundo'})
 def test_assistant_mock(self):
  import json
  r={'choices':[{'message':{'content':json.dumps({'answer':'Revisar','suggestions':[{'property_id':self.p,'title':'Janela','priority':'Alta'},{'property_id':9999,'title':'Invasão'}]})}}]}
  with patch.dict(os.environ,{'AI_API_KEY':'test-only','AI_MODEL':'test-model'}),patch.object(commercial,'call_json',return_value=r):
   x=self.m('assistant',{'question':'Registre uma pendência'});self.assertEqual(len(x['suggestions']),1);self.assertEqual(self.snap()['issues'],[])
