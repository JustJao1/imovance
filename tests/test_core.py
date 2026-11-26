import unittest,tempfile,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class Core(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); app.DB=str(Path(self.tmp.name)/'test.sqlite'); app.init()
        with app.transaction() as c:
            self.u=c.execute("INSERT INTO users(email,name,password) VALUES('a@b.com','Ana','unused')").lastrowid
            self.o=c.execute("INSERT INTO organizations(name) VALUES('A')").lastrowid
            self.other=c.execute("INSERT INTO organizations(name) VALUES('B')").lastrowid
            c.execute('INSERT INTO memberships VALUES(?,?,?)',(self.u,self.o,'owner'))
        self.p=self.m('properties',{'name':'Apto 102'})['id']
        self.i=self.m('items',{'property_id':self.p,'name':'Garfos','room':'Cozinha','category':'Utensílios','needed':12,'quantity':10,'damaged':2})['id']
    def tearDown(self): self.tmp.cleanup()
    def m(self,r,d):
        with app.transaction() as c: return app.mutate(c,self.o,self.u,r,d)
    def state(self):
        with app.connect() as c: return app.snapshot(c,self.o)
    def test_flow(self):
        s=self.state(); self.assertEqual(app.shortage(s['items'][0]),4); self.assertEqual(len(s['issues']),1)
        p=self.m('purchases',{'item_id':self.i,'quantity':4,'cost':8000})['id']
        with self.assertRaises(app.Error): self.m('purchases',{'item_id':self.i,'quantity':1})
        with self.assertRaises(app.Error): self.m('purchases/receive',{'id':p,'quantity':1})
        self.m('purchases/approve',{'id':p}); self.assertEqual(self.state()['finance'],[])
        self.m('purchases/receive',{'id':p,'quantity':2}); self.assertEqual(app.shortage(self.state()['items'][0]),2)
        self.m('purchases/pay',{'id':p,'cost':8000}); self.assertEqual(self.state()['finance'][0]['amount'],8000)
        with self.assertRaises(app.Error): self.m('purchases/pay',{'id':p,'cost':8000})
        self.m('purchases/receive',{'id':p,'quantity':2}); s=self.state(); self.assertEqual(app.shortage(s['items'][0]),0); self.assertEqual(s['issues'][0]['status'],'Aguardando conferência')
        self.m('issues/status',{'id':s['issues'][0]['id'],'status':'Resolvida','note':'Conferido'}); self.assertEqual(self.state()['issues'][0]['status'],'Resolvida')
        with self.assertRaises(app.Error): self.m('purchases/receive',{'id':p,'quantity':1})
    def test_tenant(self):
        with app.transaction() as c:
            self.assertEqual(app.snapshot(c,self.other)['properties'],[])
            with self.assertRaises(app.Error): app.mutate(c,self.other,self.u,'items',{'property_id':self.p,'name':'Invasão'})
    def test_invalid_item(self):
        with self.assertRaises(app.Error): self.m('items',{'property_id':self.p,'name':'Teste','room':'Sala','category':'X','needed':2,'quantity':1,'damaged':2})
    def test_unresolved_shortage(self):
        i=self.state()['issues'][0]['id']; self.m('issues/status',{'id':i,'status':'Aguardando conferência','note':'Teste'})
        with self.assertRaises(app.Error): self.m('issues/status',{'id':i,'status':'Resolvida','note':'Teste'})
    def test_password(self):
        h=app.encode_password('senha forte longa'); self.assertTrue(app.check_password('senha forte longa',h)); self.assertFalse(app.check_password('incorreta',h))
if __name__=='__main__': unittest.main()
