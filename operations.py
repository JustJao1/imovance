"""Property reservations and receivables, scoped to the authenticated organization."""
def extend(c,o,data):
    for k in ('reservations','receivables'):
        data[k]=[dict(r) for r in c.execute(f'SELECT * FROM {k} WHERE org_id=? ORDER BY id DESC',(o,))]
    return data

def mutate(a,c,o,u,route,d):
    if route not in ('reservations/save','reservations/status','receivables/save','receivables/status'): return None
    table=route.split('/')[0]
    if route.endswith('/save'):
        p=a.one(c,'properties',o,a.integer(d,'property_id',minval=1));a.require(not p['archived'],'Imóvel arquivado.')
        if table=='reservations':
            guest=a.string(d,'guest',required=True); arrival=a.day(d,'arrival'); departure=a.day(d,'departure'); notes=a.string(d,'notes',maxlen=3000)
            a.require(arrival and departure and arrival<departure,'A saída deve ser posterior à entrada.')
            a.require(not c.execute("SELECT 1 FROM reservations WHERE org_id=? AND property_id=? AND status!='Cancelada' AND arrival<? AND departure>?",(o,p['id'],departure,arrival)).fetchone(),'Já existe uma reserva neste período.')
            rid=c.execute("INSERT INTO reservations(org_id,property_id,guest,arrival,departure,status,notes) VALUES(?,?,?,?,?,'Confirmada',?)",(o,p['id'],guest,arrival,departure,notes)).lastrowid
            a.log(c,o,u,'Reserva cadastrada',guest);return {'id':rid}
        title=a.string(d,'title',required=True);payer=a.string(d,'payer',required=True);amount=a.money(d,'amount');due=a.day(d,'due');a.require(amount>0 and due,'Informe valor positivo e vencimento.')
        rid=c.execute("INSERT INTO receivables(org_id,property_id,title,payer,amount,due,status) VALUES(?,?,?,?,?,?,'Aberta')",(o,p['id'],title,payer,amount,due)).lastrowid
        a.log(c,o,u,'Cobrança cadastrada',title);return {'id':rid}
    rid=a.integer(d,'id',minval=1);r=a.one(c,table,o,rid)
    if table=='reservations':
        status=a.choice(d,'status',['Concluída','Cancelada']);a.require(r['status']=='Confirmada','Reserva já encerrada.')
        a.require(status!='Concluída' or r['departure']<=a.today(),'A reserva ainda não terminou.')
        c.execute('UPDATE reservations SET status=? WHERE org_id=? AND id=?',(status,o,rid));a.log(c,o,u,'Reserva '+status,r['guest']);return {'id':rid}
    status=a.choice(d,'status',['Recebida','Cancelada']);a.require(r['status']=='Aberta','Cobrança já encerrada.')
    fid=None
    if status=='Recebida':
        dt=a.day(d,'date',a.today());a.require(dt and dt<=a.today(),'Data de recebimento inválida.')
        fid=c.execute("INSERT INTO finance(org_id,property_id,kind,title,amount,date) VALUES(?,?,'Receita',?,?,?)",(o,r['property_id'],r['title'],r['amount'],dt)).lastrowid
    c.execute('UPDATE receivables SET status=?,finance_id=? WHERE org_id=? AND id=?',(status,fid,o,rid));a.log(c,o,u,'Cobrança '+status,r['title']);return {'id':rid}
