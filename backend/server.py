from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import sqlite3, os, uuid, io, csv, re, json, zipfile, shutil
import pandas as pd
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent
# Local data directory can be overridden with SEM_DATA_DIR (useful on Windows to
# point at Documents\SiteExpenseManager for easier backup by the user).
DATA = Path(os.environ.get("SEM_DATA_DIR") or (ROOT / "local_data"))
DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "site_expense_manager.sqlite3"
STATEMENTS = DATA / "statements"; DOCUMENTS = DATA / "documents"; REPORTS = DATA / "reports"
for folder in (STATEMENTS, DOCUMENTS, REPORTS): folder.mkdir(exist_ok=True)
app = FastAPI(title="Site Expense Manager — Local")
api = APIRouter(prefix="/api")

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON"); return conn
def rows(query, params=()):
    with db() as conn: return [dict(r) for r in conn.execute(query, params).fetchall()]
def one(query, params=()):
    with db() as conn:
        row = conn.execute(query, params).fetchone(); return dict(row) if row else None
def uid(): return str(uuid.uuid4())
def money(n): return round(float(n or 0), 2)

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, bank_name TEXT NOT NULL, nickname TEXT NOT NULL, last_four TEXT, account_type TEXT, active INTEGER DEFAULT 1, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS sites (id TEXT PRIMARY KEY, site_name TEXT NOT NULL, site_code TEXT NOT NULL UNIQUE, address TEXT, active INTEGER DEFAULT 1, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER DEFAULT 1, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS rules (id TEXT PRIMARY KEY, keyword TEXT NOT NULL, site_id TEXT, category_id TEXT, priority INTEGER DEFAULT 1, active INTEGER DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS statements (id TEXT PRIMARY KEY, account_id TEXT, original_filename TEXT, stored_path TEXT, statement_month INTEGER, statement_year INTEGER, uploaded_at TEXT, transaction_count INTEGER DEFAULT 0, debit_total REAL DEFAULT 0, import_status TEXT, warnings TEXT);
CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, account_id TEXT, statement_id TEXT, transaction_date TEXT, transaction_time TEXT, debit REAL DEFAULT 0, credit REAL DEFAULT 0, description TEXT, upi_reference TEXT, transaction_reference TEXT, merchant TEXT, site_id TEXT, category_id TEXT, classification_status TEXT, duplicate_status TEXT, notes TEXT, is_demo INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, transaction_id TEXT, filename TEXT, stored_path TEXT, document_type TEXT, uploaded_at TEXT);
CREATE TABLE IF NOT EXISTS month_closings (year INTEGER, month INTEGER, closed INTEGER DEFAULT 0, closed_at TEXT, PRIMARY KEY(year, month));
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

class AccountIn(BaseModel): bank_name: str; nickname: str; last_four: str = ""; account_type: str = "Current"; active: bool = True; notes: str = ""
class SiteIn(BaseModel): site_name: str; site_code: str; address: str = ""; active: bool = True; notes: str = ""
class CategoryIn(BaseModel): name: str; active: bool = True; notes: str = ""
class RuleIn(BaseModel): keyword: str; site_id: str = ""; category_id: str = ""; priority: int = 1; active: bool = True
class TransactionIn(BaseModel): site_id: str = ""; category_id: str = ""; notes: str = ""
class CloseIn(BaseModel): year: int; month: int; closed: bool

def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        if not conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone(): seed(conn)
def insert(conn, table, payload):
    keys = list(payload); conn.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", [payload[k] for k in keys])
def seed(conn):
    accounts=[{"id":uid(),"bank_name":"HDFC","nickname":"HDFC XXXX1234","last_four":"1234","account_type":"Current","active":1,"notes":"Demo account","created_at":now()},{"id":uid(),"bank_name":"SBI","nickname":"SBI XXXX5678","last_four":"5678","account_type":"Savings","active":1,"notes":"Demo account","created_at":now()}]
    sites=[{"id":uid(),"site_name":"Green Valley","site_code":"GV","address":"North Pune","active":1,"notes":"Demo site","created_at":now()},{"id":uid(),"site_name":"Sunshine Apartment","site_code":"SA","address":"West Pune","active":1,"notes":"Demo site","created_at":now()},{"id":uid(),"site_name":"Highway Project","site_code":"HW","address":"Mumbai Highway","active":1,"notes":"Demo site","created_at":now()}]
    categories=[{"id":uid(),"name":x,"active":1,"notes":"Demo category","created_at":now()} for x in ["Cement","Diesel/Fuel","Labour","Material","Transport","Electrical","Plumbing","Equipment","Food","Travel","Office","Other"]]
    for x in accounts: insert(conn,"accounts",x)
    for x in sites: insert(conn,"sites",x)
    for x in categories: insert(conn,"categories",x)
    site={x["site_code"]:x for x in sites}; cat={x["name"]:x for x in categories}
    descriptions=[("GV - CEMENT - ABC TRADERS","Cement",18500),("GV - DIESEL - HP PUMP","Diesel/Fuel",9200),("SA - LABOUR - RAJU","Labour",27600),("HW - MATERIAL - XYZ","Material",12400),("GV - TRANSPORT - TRUCK12","Transport",6800),("SA - ELECTRICAL - WIRE HOUSE","Electrical",14800),("HW - CEMENT - BUILD MART","Cement",21600),("GV - LABOUR - SHYAM","Labour",18000),("SA - MATERIAL - TILE WORLD","Material",11500),("HW - DIESEL - HP PUMP","Diesel/Fuel",8400),("GV - PLUMBING - PIPE CO","Plumbing",7200),("SA - TRANSPORT - MINI TRUCK","Transport",5600),("HW - EQUIPMENT - RENTAL","Equipment",9400),("GV - FOOD - SITE LUNCH","Food",3200),("SA - CEMENT - ABC TRADERS","Cement",16800),("HW - LABOUR - RAJU","Labour",22500),("GV - MATERIAL - STEEL HOUSE","Material",18900),("SA - OFFICE - STATIONERY","Office",2400),("HW - TRANSPORT - TRUCK12","Transport",7600),("GV - DIESEL - HP PUMP","Diesel/Fuel",8800)]
    for i,(description,category,amount) in enumerate(descriptions):
        code=description.split(" ")[0]; account=accounts[i%2]; insert(conn,"transactions",{"id":uid(),"account_id":account["id"],"statement_id":"demo-statement","transaction_date":f"2026-08-{(i%27)+1:02d}","transaction_time":"","debit":amount,"credit":0,"description":description,"upi_reference":f"DEMO{i+1:04d}","transaction_reference":f"DEMO-TXN-{i+1:03d}","merchant":description.split(" - ")[-1],"site_id":site[code]["id"],"category_id":cat[category]["id"],"classification_status":"Classified","duplicate_status":"Clear","notes":"Demo transaction — safe to delete","is_demo":1,"created_at":now()})
    insert(conn,"settings",{"key":"company_name","value":"Site Expense Manager"}); insert(conn,"settings",{"key":"currency","value":"INR"})

def classify(description, rules):
    site_id=category_id=""
    for rule in sorted(rules, key=lambda x:(x.get("priority",1), -len(x.get("keyword", "")))):
        if rule["keyword"].lower() in description.lower():
            if rule.get("site_id"): site_id=rule["site_id"]
            if rule.get("category_id"): category_id=rule["category_id"]
    return site_id, category_id, "Classified" if site_id and category_id else "Needs Review"
def parse_pdf(content):
    text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)
    records=[]
    for line in text.splitlines():
        match=re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}).*?([0-9,]+\.\d{2})\s*(.*)$", line)
        if match: records.append({"date":match.group(1),"amount":match.group(2).replace(",",""),"description":match.group(3).strip()})
    return records
def parse_statement(filename, content):
    if filename.lower().endswith(".pdf"): return parse_pdf(content), "PDF text extraction completed; scanned PDFs may need manual mapping"
    df=pd.read_csv(io.BytesIO(content)) if filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(content))
    columns={str(c).lower().strip():c for c in df.columns}; date_col=next((columns[k] for k in columns if "date" in k),None); desc_col=next((columns[k] for k in columns if any(w in k for w in ["description","narration","remark","particular"])),None); debit_col=next((columns[k] for k in columns if any(w in k for w in ["debit","withdrawal","amount","paid"])),None); credit_col=next((columns[k] for k in columns if "credit" in k),None); upi_col=next((columns[k] for k in columns if "upi" in k or "reference" in k),None)
    if not date_col or not desc_col or not debit_col: raise ValueError("Map date, description, and debit/amount columns to import this file")
    return [{"date":str(r[date_col])[:10],"amount":str(r[debit_col]),"credit":str(r[credit_col]) if credit_col else "0","description":str(r[desc_col]),"upi":str(r[upi_col]) if upi_col else ""} for _,r in df.iterrows()], ""

@api.get("/")
async def root(): return {"message":"Site Expense Manager local API","database":"SQLite","offline_ready":True}
@api.get("/dashboard")
async def dashboard(month:int=8,year:int=2026):
    tx=rows("SELECT * FROM transactions WHERE substr(transaction_date,1,4)=? AND substr(transaction_date,6,2)=?",(str(year),f"{month:02d}")); accounts=rows("SELECT * FROM accounts WHERE active=1"); sites=rows("SELECT * FROM sites WHERE active=1"); cats=rows("SELECT * FROM categories WHERE active=1")
    def totals(key, lookup): return [{"name":x.get("name") or x.get("site_name") or x.get("nickname"),"amount":money(sum(t["debit"] for t in tx if t.get(key)==x["id"]))} for x in lookup]
    return {"month":month,"year":year,"summary":{"total":money(sum(t["debit"] for t in tx)),"transactions":len(tx),"statements":len(rows("SELECT * FROM statements WHERE statement_year=? AND statement_month=?",(year,month))),"accounts":len(accounts),"sites":len(sites),"review":sum(t["classification_status"]!="Classified" for t in tx),"duplicates":sum(t["duplicate_status"]=="Possible Duplicate" for t in tx)},"site_totals":totals("site_id",sites),"category_totals":totals("category_id",cats),"account_totals":totals("account_id",accounts),"recent":tx[:8]}
@api.get("/accounts")
async def accounts(): return rows("SELECT * FROM accounts ORDER BY bank_name,nickname")
@api.post("/accounts")
async def create_account(data:AccountIn):
    item={"id":uid(),**data.model_dump(),"active":int(data.active),"created_at":now()}
    with db() as c: insert(c,"accounts",item)
    return item
@api.get("/sites")
async def sites(): return rows("SELECT * FROM sites ORDER BY site_name")
@api.post("/sites")
async def create_site(data:SiteIn):
    item={"id":uid(),**data.model_dump(),"active":int(data.active),"created_at":now()}
    with db() as c: insert(c,"sites",item)
    return item
@api.get("/categories")
async def categories(): return rows("SELECT * FROM categories ORDER BY name")
@api.post("/categories")
async def create_category(data:CategoryIn):
    item={"id":uid(),**data.model_dump(),"active":int(data.active),"created_at":now()}
    with db() as c: insert(c,"categories",item)
    return item
@api.get("/rules")
async def rules(): return rows("SELECT r.*,s.site_name,c.name category_name FROM rules r LEFT JOIN sites s ON s.id=r.site_id LEFT JOIN categories c ON c.id=r.category_id ORDER BY priority")
@api.post("/rules")
async def create_rule(data:RuleIn):
    item={"id":uid(),**data.model_dump(),"active":int(data.active),"created_at":now()}
    with db() as c: insert(c,"rules",item)
    return item
@api.get("/transactions")
async def transactions(month:str="",account_id:str="",site_id:str="",category_id:str="",status:str="",search:str=""):
    query="SELECT t.*,a.nickname account_name,s.site_name,c.name category_name FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id LEFT JOIN sites s ON s.id=t.site_id LEFT JOIN categories c ON c.id=t.category_id WHERE 1=1"; params=[]
    if month: query+=" AND substr(t.transaction_date,1,7)=?"; params.append(month)
    for field,value in [("t.account_id",account_id),("t.site_id",site_id),("t.category_id",category_id),("t.classification_status",status)]:
        if value: query+=f" AND {field}=?"; params.append(value)
    if search: query+=" AND (t.description LIKE ? OR t.upi_reference LIKE ? OR t.merchant LIKE ? OR t.notes LIKE ?)"; params += [f"%{search}%"]*4
    return rows(query+" ORDER BY t.transaction_date DESC",params)
@api.patch("/transactions/{txn_id}")
async def update_transaction(txn_id:str,data:TransactionIn):
    status="Classified" if data.site_id and data.category_id else "Needs Review"
    with db() as c: c.execute("UPDATE transactions SET site_id=?,category_id=?,notes=?,classification_status=? WHERE id=?",(data.site_id,data.category_id,data.notes,status,txn_id))
    return one("SELECT * FROM transactions WHERE id=?",(txn_id,))
@api.get("/statements")
async def statements(): return rows("SELECT st.*,a.nickname account_name FROM statements st LEFT JOIN accounts a ON a.id=st.account_id ORDER BY uploaded_at DESC")
@api.post("/statements/upload")
async def upload_statement(account_id:str=Form(...),statement_month:int=Form(...),statement_year:int=Form(...),file:UploadFile=File(...)):
    content=await file.read(); statement_id=uid(); stored=STATEMENTS/f"{statement_id}_{file.filename}"; stored.write_bytes(content)
    try: records,warnings=parse_statement(file.filename,content)
    except Exception as exc: records=[]; warnings=str(exc)
    ruleset=rows("SELECT * FROM rules WHERE active=1"); imported=[]; duplicates=0
    for r in records:
        amount=money(re.sub(r"[^0-9.-]","",r.get("amount","0")) or 0); description=r.get("description",""); site_id,category_id,status=classify(description,ruleset); duplicate=one("SELECT id FROM transactions WHERE account_id=? AND transaction_date=? AND debit=? AND (upi_reference=? OR description=?)",(account_id,r.get("date",""),amount,r.get("upi",""),description)); duplicate_status="Possible Duplicate" if duplicate else "Clear"; duplicates+=bool(duplicate)
        imported.append({"id":uid(),"account_id":account_id,"statement_id":statement_id,"transaction_date":r.get("date",""),"transaction_time":"","debit":amount,"credit":money(re.sub(r"[^0-9.-]","",r.get("credit","0")) or 0),"description":description,"upi_reference":r.get("upi",""),"transaction_reference":"","merchant":"","site_id":site_id,"category_id":category_id,"classification_status":status,"duplicate_status":duplicate_status,"notes":"","is_demo":0,"created_at":now()})
    with db() as c:
        for item in imported: insert(c,"transactions",item)
        insert(c,"statements",{"id":statement_id,"account_id":account_id,"original_filename":file.filename,"stored_path":str(stored),"statement_month":statement_month,"statement_year":statement_year,"uploaded_at":now(),"transaction_count":len(imported),"debit_total":sum(x["debit"] for x in imported),"import_status":"Imported" if records else "Needs Mapping","warnings":warnings})
    return {"id":statement_id,"imported":len(imported),"total":sum(x["debit"] for x in imported),"classified":sum(x["classification_status"]=="Classified" for x in imported),"review":sum(x["classification_status"]=="Needs Review" for x in imported),"duplicates":duplicates,"warnings":warnings}
@api.get("/statements/{statement_id}/download")
async def download_statement(statement_id:str):
    item=one("SELECT * FROM statements WHERE id=?",(statement_id,))
    if not item or not Path(item["stored_path"]).exists(): raise HTTPException(404,"Original statement not found")
    return FileResponse(item["stored_path"],filename=item["original_filename"])
@api.get("/reports/summary")
async def report_summary(month:str="2026-08"):
    tx=rows("SELECT t.*,a.nickname account_name,s.site_name,c.name category_name FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id LEFT JOIN sites s ON s.id=t.site_id LEFT JOIN categories c ON c.id=t.category_id WHERE substr(transaction_date,1,7)=? ORDER BY transaction_date",(month,))
    def group(key):
        out={}
        for t in tx: out[t.get(key) or "Unassigned"]=out.get(t.get(key) or "Unassigned",0)+t["debit"]
        return [{"name":k,"amount":money(v)} for k,v in out.items()]
    y,m=(int(x) for x in month.split("-")) if "-" in month else (0,0)
    closing=one("SELECT closed FROM month_closings WHERE year=? AND month=?",(y,m))
    return {"month":month,"total":money(sum(x["debit"] for x in tx)),"transactions":len(tx),"by_site":group("site_name"),"by_category":group("category_name"),"by_account":group("account_name"),"transactions_data":tx,"closed":bool(closing and closing["closed"])}
@api.get("/reports/export.xlsx")
async def export_xlsx(month:str=""):
    query="SELECT t.transaction_date Date,a.bank_name Bank,a.nickname Account,t.description Description,t.debit Amount,s.site_name Site,c.name Category,t.upi_reference UPI_Reference,t.merchant Merchant,t.notes Notes FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id LEFT JOIN sites s ON s.id=t.site_id LEFT JOIN categories c ON c.id=t.category_id"; params=()
    if month: query+=" WHERE substr(t.transaction_date,1,7)=?"; params=(month,)
    frame=pd.DataFrame(rows(query,params)); path=REPORTS/f"SiteExpense_{month or 'all'}.xlsx"; frame.to_excel(path,index=False); return FileResponse(path,filename=path.name)
@api.get("/reports/export.pdf")
async def export_pdf(month:str=""):
    data=await report_summary(month or datetime.now().strftime("%Y-%m")); path=REPORTS/f"SiteExpense_{month or 'all'}.pdf"; c=canvas.Canvas(str(path),pagesize=A4); c.setFont("Helvetica-Bold",18); c.drawString(48,790,"Site Expense Manager"); c.setFont("Helvetica",11); c.drawString(48,770,f"Monthly report · {month or 'All transactions'}"); c.setFont("Helvetica-Bold",14); c.drawString(48,725,f"Total expenses: ₹{data['total']:,.2f}"); c.setFont("Helvetica",11); y=690; c.drawString(48,y,f"Transactions: {data['transactions']}"); y-=30; c.setFont("Helvetica-Bold",12); c.drawString(48,y,"Site-wise expenses"); y-=22; c.setFont("Helvetica",10)
    for item in data["by_site"][:12]: c.drawString(62,y,f"{item['name']}: ₹{item['amount']:,.2f}"); y-=18
    c.save(); return FileResponse(path,filename=path.name)
@api.post("/documents")
async def upload_document(transaction_id:str=Form(...),file:UploadFile=File(...)):
    path=DOCUMENTS/f"{uid()}_{file.filename}"; path.write_bytes(await file.read()); item={"id":uid(),"transaction_id":transaction_id,"filename":file.filename,"stored_path":str(path),"document_type":file.content_type or "file","uploaded_at":now()}
    with db() as c: insert(c,"documents",item)
    return item
@api.get("/documents/{transaction_id}")
async def documents(transaction_id:str): return rows("SELECT id,transaction_id,filename,document_type,uploaded_at FROM documents WHERE transaction_id=?",(transaction_id,))
@api.get("/backup")
async def backup():
    path=REPORTS/f"SiteExpenseBackup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.zip"
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(DB_PATH,"site_expense_manager.sqlite3")
        for folder in (STATEMENTS,DOCUMENTS):
            for f in folder.iterdir(): z.write(f,f"{folder.name}/{f.name}")
    return FileResponse(path,filename=path.name)
@api.post("/restore")
async def restore(file:UploadFile=File(...)):
    content=await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names=set(z.namelist())
            if "site_expense_manager.sqlite3" not in names: raise HTTPException(400,"ZIP does not contain site_expense_manager.sqlite3")
            for f in STATEMENTS.iterdir(): f.unlink()
            for f in DOCUMENTS.iterdir(): f.unlink()
            z.extract("site_expense_manager.sqlite3", DATA)
            for name in names:
                if name.startswith("statements/") and not name.endswith("/"): z.extract(name, DATA)
                elif name.startswith("documents/") and not name.endswith("/"): z.extract(name, DATA)
    except zipfile.BadZipFile: raise HTTPException(400,"Uploaded file is not a valid backup ZIP")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(400,f"Restore failed: {exc}")
    return {"restored":True,"transactions":len(rows("SELECT id FROM transactions")),"accounts":len(rows("SELECT id FROM accounts")),"sites":len(rows("SELECT id FROM sites"))}
@api.post("/sample-data/delete")
async def delete_sample_data():
    with db() as c: c.execute("DELETE FROM transactions WHERE is_demo=1"); c.execute("DELETE FROM accounts WHERE notes='Demo account'"); c.execute("DELETE FROM sites WHERE notes='Demo site'"); c.execute("DELETE FROM categories WHERE notes='Demo category'")
    return {"deleted":True}
@api.get("/settings")
async def settings(): return {x["key"]:x["value"] for x in rows("SELECT * FROM settings")}
@api.post("/month-close")
async def month_close(data:CloseIn):
    with db() as c: c.execute("INSERT OR REPLACE INTO month_closings(year,month,closed,closed_at) VALUES(?,?,?,?)",(data.year,data.month,int(data.closed),now()))
    return {"year":data.year,"month":data.month,"closed":data.closed}

@app.on_event("startup")
async def startup(): init_db()
app.include_router(api)
# Allow local access (Windows) as well as the Emergent preview host.
_extra_origins = [o.strip() for o in os.environ.get("SEM_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:5555","http://127.0.0.1:5555","https://site-spend-central.preview.emergentagent.com",*_extra_origins],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
# When a built React app is bundled next to the backend (frontend/build), serve
# it from the same port so the whole app works via one URL on Windows.
_BUILD = ROOT.parent / "frontend" / "build"
if _BUILD.exists():
    app.mount("/static", StaticFiles(directory=_BUILD / "static"), name="static")
    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = _BUILD / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_BUILD / "index.html")