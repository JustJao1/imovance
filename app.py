import commercial, operations, sys
import os, sqlite3, json, secrets, hashlib, hmac, time, re, logging
from datetime import date, datetime, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
ROOT=Path(__file__).resolve().parent
DB=os.environ.get('IMOVEL_DB',str(ROOT/'data.sqlite3'))
SECURE=os.environ.get('COOKIE_SECURE')=='1'
ORIGIN=os.environ.get('APP_ORIGIN','http://localhost:8000')
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def today(): return date.today().isoformat()
class ManagedConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()
def connect():
    c=sqlite3.connect(DB,timeout=15,factory=ManagedConnection); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
@contextmanager
def transaction():
    c=connect()
    try:
        c.execute('BEGIN IMMEDIATE'); yield c; c.commit()
    except: c.rollback(); raise
    finally: c.close()
def init():
    with connect() as c: c.executescript((ROOT/'schema.sql').read_text()); c.execute('PRAGMA journal_mode=WAL')
class Error(Exception):
    def __init__(self,msg,status=400): self.msg=msg; self.status=status

def require(v,msg='Dados inválidos.'):
    if not v: raise Error(msg)
def string(d,k,default='',maxlen=300,required=False):
    v=d.get(k,default); require(isinstance(v,str),f'Campo {k} inválido.'); v=v.strip(); require(len(v)<=maxlen and (v or not required),f'Confira o campo {k}.'); return v

def integer(d,k,default=None,minval=0,maxval=1000000):
    v=d.get(k,default); require(type(v) is int and minval<=v<=maxval,f'Confira o campo {k}.'); return v

def money(d,k): return integer(d,k,0,0,100000000000)
def day(d,k,default=None):
    v=d.get(k,default)
    if not v: return None
    try: return date.fromisoformat(v).isoformat()
    except: raise Error('Data inválida.')
def choice(d,k,options,default=None):
    v=d.get(k,default); require(v in options,f'Opção inválida: {k}.'); return v

def encode_password(p):
    salt=secrets.token_hex(16); return salt+':'+hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def check_password(p,stored):
    salt,digest=stored.split(':'); return hmac.compare_digest(digest,hashlib.scrypt(p.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex())
def token_hash(t): return hashlib.sha256(t.encode()).hexdigest()
def one(c,table,org,id):
    r=c.execute(f'SELECT * FROM {table} WHERE org_id=? AND id=?',(org,id)).fetchone()
    if not r: raise Error('Registro não encontrado.',404)
    return r

def log(c,o,u,action,details): c.execute('INSERT INTO audit(org_id,user_id,action,details,created) VALUES(?,?,?,?,?)',(o,u,action,details,now()))
def create_session(c,u,o):
    t=secrets.token_urlsafe(32); c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),)); c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(t),u,o,int(time.time())+86400*7)); return t

def shortage(i): return max(0,i['needed']-i['quantity']+i['damaged'])
def sync_issue(c,o,i):
    gap=shortage(i); issue=c.execute("SELECT * FROM issues WHERE org_id=? AND item_id=? AND status NOT IN ('Resolvida','Cancelada')",(o,i['id'])).fetchone()
    if gap>0:
        if issue:
            c.execute("UPDATE issues SET description=?,status=CASE WHEN status='Aguardando conferência' THEN 'Aberta' ELSE status END WHERE id=?",(f'Reposição necessária: {gap} unidade(s).',issue['id']))
            return issue['id']
        return c.execute('INSERT INTO issues(org_id,property_id,item_id,title,description,priority,status,created) VALUES(?,?,?,?,?,?,?,?)',(o,i['property_id'],i['id'],'Repor '+i['name'],f'Reposição necessária: {gap} unidade(s).','Normal','Aberta',now())).lastrowid
    if issue: c.execute("UPDATE issues SET status='Aguardando conferência',description='Quantidade necessária atingida. Confirme a reposição.' WHERE id=?",(issue['id'],))
    return issue['id'] if issue else None

def snapshot(c,o):
    def rows(q): return [dict(r) for r in c.execute(q,(o,))]
    return {'properties':rows('SELECT * FROM properties WHERE org_id=? ORDER BY archived,name'), 'items':rows('SELECT * FROM items WHERE org_id=? ORDER BY name'), 'issues':rows('SELECT * FROM issues WHERE org_id=? ORDER BY id DESC'), 'purchases':rows('SELECT * FROM purchases WHERE org_id=? ORDER BY id DESC'), 'finance':rows('SELECT * FROM finance WHERE org_id=? ORDER BY date DESC,id DESC'), 'audit':rows('SELECT audit.*,users.name AS actor FROM audit JOIN users ON users.id=audit.user_id WHERE audit.org_id=? ORDER BY audit.id DESC LIMIT 200')}

def mutate(c,o,u,route,d):
    if route=='properties' and not d.get('id') or route=='properties/archive' and d.get('archived')==0:
        require(c.execute('SELECT COUNT(*) FROM properties WHERE org_id=? AND archived=0',(o,)).fetchone()[0]<commercial.billing(c,o)['limit'],'Limite de imóveis ativos do plano atingido.')
    op=operations.mutate(sys.modules[__name__],c,o,u,route,d)
    if op is not None:return op
    extra=commercial.mutate_ext(sys.modules[__name__],c,o,u,route,d)
    if extra is not None:return extra
    if route=='properties':
        name=string(d,'name',required=True); kind=choice(d,'kind',['Apartamento','Casa','Kitnet','Comercial','Outro'],'Apartamento'); occ=choice(d,'occupancy',['Disponível','Ocupado','Indisponível'],'Disponível'); addr=string(d,'address'); id=d.get('id')
        if id is not None: one(c,'properties',o,integer(d,'id',minval=1)); c.execute('UPDATE properties SET name=?,address=?,kind=?,occupancy=? WHERE org_id=? AND id=?',(name,addr,kind,occ,o,id))
        else: id=c.execute('INSERT INTO properties(org_id,name,address,kind,occupancy) VALUES(?,?,?,?,?)',(o,name,addr,kind,occ)).lastrowid
        log(c,o,u,'Imóvel salvo',name); return {'id':id}
    if route=='properties/archive':
        id=integer(d,'id',minval=1); p=one(c,'properties',o,id); archived=integer(d,'archived',maxval=1); c.execute('UPDATE properties SET archived=? WHERE org_id=? AND id=?',(archived,o,id)); log(c,o,u,'Imóvel arquivado' if archived else 'Imóvel restaurado',p['name']); return {'id':id}
    if route=='items':
        prop=one(c,'properties',o,integer(d,'property_id',minval=1)); require(not prop['archived'],'Imóvel arquivado.'); name=string(d,'name',required=True); room=string(d,'room',required=True); cat=string(d,'category',required=True); need=integer(d,'needed'); qty=integer(d,'quantity'); damaged=integer(d,'damaged',0,maxval=qty); id=d.get('id')
        if id is not None:
            old=one(c,'items',o,integer(d,'id',minval=1)); require(old['property_id']==prop['id'],'Não é possível transferir por edição.'); c.execute('UPDATE items SET name=?,room=?,category=?,needed=?,quantity=?,damaged=? WHERE org_id=? AND id=?',(name,room,cat,need,qty,damaged,o,id))
        else: id=c.execute('INSERT INTO items(org_id,property_id,name,room,category,needed,quantity,damaged) VALUES(?,?,?,?,?,?,?,?)',(o,prop['id'],name,room,cat,need,qty,damaged)).lastrowid
        sync_issue(c,o,one(c,'items',o,id)); log(c,o,u,'Inventário conferido',f'{prop["name"]}: {name} ({qty} existentes, {damaged} danificados, {need} necessários)'); return {'id':id}
    if route=='issues':
        p=one(c,'properties',o,integer(d,'property_id',minval=1)); require(not p['archived'],'Imóvel arquivado.'); title=string(d,'title',required=True); desc=string(d,'description',maxlen=3000); priority=choice(d,'priority',['Baixa','Normal','Alta','Urgente'],'Normal'); due=day(d,'due'); id=c.execute('INSERT INTO issues(org_id,property_id,title,description,priority,status,due,created) VALUES(?,?,?,?,?,?,?,?)',(o,p['id'],title,desc,priority,'Aberta',due,now())).lastrowid; log(c,o,u,'Pendência criada',title); return {'id':id}
    if route=='issues/status':
        i=one(c,'issues',o,integer(d,'id',minval=1)); status=choice(d,'status',['Aberta','Em andamento','Aguardando conferência','Resolvida','Cancelada']); note=string(d,'note',maxlen=1000,required=True); allowed={'Aberta':['Em andamento','Aguardando conferência','Cancelada'],'Em andamento':['Aberta','Aguardando conferência','Cancelada'],'Aguardando conferência':['Resolvida','Aberta','Cancelada'],'Resolvida':['Aberta'],'Cancelada':['Aberta']}; require(status in allowed[i['status']],'Transição de situação inválida.')
        if status=='Resolvida' and i['item_id']: require(shortage(one(c,'items',o,i['item_id']))==0,'Ainda há itens em falta.');
        c.execute('UPDATE issues SET status=? WHERE org_id=? AND id=?',(status,o,i['id'])); log(c,o,u,'Pendência: '+status,i['title']+' — '+note); return {'id':i['id']}
    if route=='purchases':
        i=one(c,'items',o,integer(d,'item_id',minval=1)); require(not one(c,'properties',o,i['property_id'])['archived'],'Imóvel arquivado.'); qty=integer(d,'quantity',minval=1); pending=c.execute("SELECT COALESCE(SUM(quantity-received),0) FROM purchases WHERE org_id=? AND item_id=? AND status NOT IN ('Recebida','Cancelada')",(o,i['id'])).fetchone()[0]; require(qty<=max(0,shortage(i)-pending),'Quantidade supera a necessidade ainda não coberta.'); cost=money(d,'cost'); issue=sync_issue(c,o,i); id=c.execute('INSERT INTO purchases(org_id,item_id,issue_id,quantity,cost,status,created) VALUES(?,?,?,?,?,?,?)',(o,i['id'],issue,qty,cost,'Solicitada',now())).lastrowid; log(c,o,u,'Compra solicitada',f'{qty} × {i["name"]}'); return {'id':id}
    if route.startswith('purchases/'):
        p=one(c,'purchases',o,integer(d,'id',minval=1)); i=one(c,'items',o,p['item_id']); action=route.split('/')[1]
        if action=='approve': require(p['status']=='Solicitada','Compra não está aguardando aprovação.'); c.execute("UPDATE purchases SET status='Aprovada' WHERE id=?",(p['id'],))
        elif action=='cancel': require(p['status'] in ['Solicitada','Aprovada'] and not p['paid'] and not p['received'],'Não é possível cancelar uma compra paga ou recebida.'); c.execute("UPDATE purchases SET status='Cancelada' WHERE id=?",(p['id'],))
        elif action=='receive':
            require(p['status'] in ['Aprovada','Parcialmente recebida'],'Compra precisa estar aprovada.'); qty=integer(d,'quantity',minval=1,maxval=p['quantity']-p['received']); total=p['received']+qty; status='Recebida' if total==p['quantity'] else 'Parcialmente recebida'; c.execute('UPDATE purchases SET received=?,status=? WHERE id=?',(total,status,p['id'])); c.execute('UPDATE items SET quantity=quantity+? WHERE id=?',(qty,i['id'])); sync_issue(c,o,one(c,'items',o,i['id']))
        elif action=='pay':
            require(p['status'] in ['Aprovada','Parcialmente recebida','Recebida'] and not p['paid'],'Pagamento não permitido.'); cost=money(d,'cost'); require(cost>0,'Informe o valor pago.'); dt=day(d,'date',today()); require(dt is not None,'Informe a data.'); c.execute('INSERT INTO finance(org_id,property_id,purchase_id,kind,title,amount,date) VALUES(?,?,?,?,?,?,?)',(o,i['property_id'],p['id'],'Despesa','Compra: '+i['name'],cost,dt)); c.execute('UPDATE purchases SET paid=1,cost=? WHERE id=?',(cost,p['id']))
        else: raise Error('Rota desconhecida.',404)
        log(c,o,u,{'approve':'Compra aprovada','cancel':'Compra cancelada','receive':'Recebimento confirmado','pay':'Pagamento registrado'}[action],i['name']+f' · compra {p["id"]}'); return {'id':p['id']}
    if route=='finance':
        p=one(c,'properties',o,integer(d,'property_id',minval=1)); title=string(d,'title',required=True); kind=choice(d,'kind',['Receita','Despesa']); amount=money(d,'amount'); require(amount>0,'Informe um valor positivo.'); dt=day(d,'date',today()); require(dt is not None,'Informe a data.'); id=c.execute('INSERT INTO finance(org_id,property_id,kind,title,amount,date) VALUES(?,?,?,?,?,?)',(o,p['id'],kind,title,amount,dt)).lastrowid; log(c,o,u,'Lançamento financeiro',title); return {'id':id}
    raise Error('Rota desconhecida.',404)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): logging.info('%s %s',self.command,urlsplit(self.path).path)
    def send(self,status,data,ctype='application/json; charset=utf-8',cookie=None):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie is not None: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(data)
    def cookie(self,t): return f'session={t}; Path=/; HttpOnly; SameSite=Strict; Max-Age={604800 if t else 0}'+('; Secure' if SECURE else '')
    def auth(self,c):
        ck=SimpleCookie(); ck.load(self.headers.get('Cookie','')); t=ck.get('session');
        if not t: raise Error('Entre para continuar.',401)
        s=c.execute('SELECT sessions.*,users.name,users.email,organizations.name AS organization,memberships.role FROM sessions JOIN users ON users.id=sessions.user_id JOIN organizations ON organizations.id=sessions.org_id JOIN memberships ON memberships.user_id=sessions.user_id AND memberships.org_id=sessions.org_id WHERE token=? AND expires>?',(token_hash(t.value),int(time.time()))).fetchone()
        if not s: raise Error('Sessão expirada.',401)
        return s
    def do_GET(self):
        try:
            path=urlsplit(self.path).path
            files={'/demo':('demo.html','text/html; charset=utf-8'),'/':('index.html','text/html; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8')}
            if path in files:
                f,ct=files[path]; return self.send(200,(ROOT/'static'/f).read_bytes(),ct)
            if path=='/api/state':
                with connect() as c:
                    s=self.auth(c); data=operations.extend(c,s['org_id'],commercial.extend_snapshot(c,s['org_id'],snapshot(c,s['org_id']))); data['user']={k:s[k] for k in ['name','email','organization','role']}; return self.send(200,data)
            raise Error('Página não encontrada.',404)
        except Error as e: self.send(e.status,{'error':e.msg})
        except Exception: logging.exception('GET'); self.send(500,{'error':'Não foi possível consultar os dados.'})
    def do_POST(self):
        try:
            require(self.headers.get('Origin')==ORIGIN,'Origem não autorizada.'); require(self.headers.get('Content-Type','').split(';')[0]=='application/json','Formato inválido.'); length=int(self.headers.get('Content-Length','0')); require(0<length<=65536,'Requisição inválida.'); d=json.loads(self.rfile.read(length)); require(isinstance(d,dict)); path=urlsplit(self.path).path; cookie=None
            with transaction() as c:
                if path=='/api/register':
                    email=string(d,'email',maxlen=254,required=True).lower(); require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email),'E-mail inválido.'); password=string(d,'password',maxlen=128,required=True); require(len(password)>=12,'Use pelo menos 12 caracteres.'); name=string(d,'name',required=True); org=string(d,'organization',required=True); require(not c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(),'Não foi possível criar a conta com esses dados.'); u=c.execute('INSERT INTO users(email,name,password) VALUES(?,?,?)',(email,name,encode_password(password))).lastrowid; o=c.execute('INSERT INTO organizations(name) VALUES(?)',(org,)).lastrowid; c.execute('INSERT INTO memberships VALUES(?,?,?)',(u,o,'owner')); cookie=self.cookie(create_session(c,u,o)); result={'ok':True}
                elif path=='/api/login':
                    email=string(d,'email',maxlen=254).lower(); password=string(d,'password',maxlen=128); u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); require(u and check_password(password,u['password']),'E-mail ou senha incorretos.'); o=c.execute('SELECT org_id FROM memberships WHERE user_id=? ORDER BY org_id LIMIT 1',(u['id'],)).fetchone(); require(o,'Conta sem organização.'); cookie=self.cookie(create_session(c,u['id'],o['org_id'])); result={'ok':True}
                else:
                    s=self.auth(c); o=s['org_id']; u=s['user_id']
                    if path=='/api/logout': c.execute('DELETE FROM sessions WHERE token=?',(s['token'],)); cookie=self.cookie(''); result={'ok':True}
                    else:
                        require(s['role'] in ['owner','manager'],'Sem permissão.'); require(path.startswith('/api/'),'Rota inválida.'); route=path[5:]; key=self.headers.get('Idempotency-Key',''); require(8<=len(key)<=100,'Identificador da operação ausente.'); body=json.dumps(d,sort_keys=True,ensure_ascii=False); old=c.execute('SELECT * FROM mutations WHERE org_id=? AND key=?',(o,key)).fetchone()
                        if old: require(old['route']==route and old['body']==body,'Identificador já utilizado em outra operação.'); result=json.loads(old['response'])
                        else: result=mutate(c,o,u,route,d); c.execute('INSERT INTO mutations VALUES(?,?,?,?,?)',(o,key,route,body,json.dumps(result)))
            self.send(200,result,cookie=cookie)
        except Error as e: self.send(e.status,{'error':e.msg})
        except (ValueError,TypeError,sqlite3.IntegrityError): self.send(400,{'error':'Dados inválidos ou operação conflitante.'})
        except Exception: logging.exception('POST'); self.send(500,{'error':'Não foi possível salvar. Confira os dados antes de tentar novamente.'})
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO); init(); port=int(os.environ.get('PORT','8000')); print(f'Imovance: {ORIGIN}',flush=True); ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),port),Handler).serve_forever()
