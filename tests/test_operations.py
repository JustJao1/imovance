import unittest,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app,operations
class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();app.DB=str(Path(self.tmp.name)/'test.sqlite');app.init()
        with app.transaction() as c:
            self.u=c.execute("INSERT INTO users(email,name,password) VALUES('ops@example.com','Teste','unused')").lastrowid
            self.o=c.execute("INSERT INTO organizations(name) VALUES('A')").lastrowid
            self.other=c.execute("INSERT INTO organizations(name) VALUES('B')").lastrowid
            c.execute('INSERT INTO memberships VALUES(?,?,?)',(self.u,self.o,'owner'))
        self.p=self.m('properties',{'name':'Casa'})['id']
    def tearDown(self):self.tmp.cleanup()
    def m(self,route,d,org=None):
        with app.transaction() as c:return app.mutate(c,org or self.o,self.u,route,d)
    def snapshot(self):
        with app.connect() as c:return operations.extend(c,self.o,app.snapshot(c,self.o))
    def book(self,arrival='2027-01-01',departure='2027-01-05',org=None):
        return self.m('reservations/save',{'property_id':self.p,'guest':'Teste','arrival':arrival,'departure':departure},org)['id']
    def test_booking_overlap_and_boundary(self):
        r=self.book()
        with self.assertRaises(app.Error):self.book('2027-01-03','2027-01-07')
        self.book('2027-01-05','2027-01-07')
        self.m('reservations/status',{'id':r,'status':'Cancelada'})
        self.book('2027-01-01','2027-01-05')
        self.assertEqual(len(self.snapshot()['reservations']),3)
    def test_dates_and_isolation(self):
        with self.assertRaises(app.Error):self.book('2027-01-05','2027-01-01')
        with self.assertRaises(app.Error):self.book(org=self.other)
        r=self.book()
        with self.assertRaises(app.Error):self.m('reservations/status',{'id':r,'status':'Cancelada'},self.other)
        with self.assertRaises(app.Error):self.m('reservations/status',{'id':r,'status':'Concluída'})
    def test_receivable_exactly_once(self):
        r=self.m('receivables/save',{'property_id':self.p,'title':'Aluguel','payer':'Teste','amount':150050,'due':app.today()})['id']
        self.assertEqual(self.snapshot()['finance'],[])
        with self.assertRaises(app.Error):self.m('receivables/status',{'id':r,'status':'Recebida'},self.other)
        self.m('receivables/status',{'id':r,'status':'Recebida','date':app.today()})
        with self.assertRaises(app.Error):self.m('receivables/status',{'id':r,'status':'Recebida'})
        s=self.snapshot();self.assertEqual(len(s['finance']),1);self.assertEqual(s['finance'][0]['amount'],150050);self.assertEqual(s['receivables'][0]['finance_id'],s['finance'][0]['id'])
    def test_cancellation_no_income(self):
        r=self.m('receivables/save',{'property_id':self.p,'title':'Aluguel','payer':'Teste','amount':100,'due':app.today()})['id']
        self.m('receivables/status',{'id':r,'status':'Cancelada'});self.assertEqual(self.snapshot()['finance'],[])
        with self.assertRaises(app.Error):self.m('receivables/status',{'id':r,'status':'Recebida'})
if __name__=='__main__':unittest.main()
