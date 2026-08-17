from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
import os, uuid, io, logging, bcrypt, jwt, pandas as pd

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
app = FastAPI(title="Site Expense Manager")
api = APIRouter(prefix="/api")
JWT_ALGORITHM = "HS256"

def now(): return datetime.now(timezone.utc).isoformat()
def safe(doc):
    doc = dict(doc); doc.pop("_id", None); return doc
def hash_password(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verify_password(password, hashed): return bcrypt.checkpw(password.encode(), hashed.encode())
def token(user):
    return jwt.encode({"sub": user["id"], "exp": datetime.now(timezone.utc)+timedelta(hours=8)}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

async def current_user(request: Request):
    value = request.cookies.get("access_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not value: raise HTTPException(401, "Not authenticated")
    try: payload = jwt.decode(value, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError: raise HTTPException(401, "Session expired")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user or not user.get("active", True): raise HTTPException(401, "User not found")
    return user

async def admin_only(user=Depends(current_user)):
    if user["role"] != "admin": raise HTTPException(403, "Admin access required")
    return user

class Login(BaseModel): email: str; password: str
class UserCreate(BaseModel): name: str; email: str; password: str; role: str = "employee"; phone: str = ""
class SimpleCreate(BaseModel): name: str
class SiteCreate(BaseModel): site_name: str; site_code: str; address: str = ""
class RuleCreate(BaseModel): keyword: str; site_id: str; category_id: str; priority: int = 1
class TransactionUpdate(BaseModel): site_id: Optional[str] = None; category_id: Optional[str] = None; notes: str = ""

@api.get("/")
async def root(): return {"message": "Site Expense Manager API"}

@api.post("/auth/login")
async def login(data: Login, response: Response):
    user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not user or not verify_password(data.password, user["password_hash"]): raise HTTPException(401, "Invalid email or password")
    user.pop("password_hash", None); response.set_cookie("access_token", token(user), httponly=True, samesite="lax", max_age=28800)
    return user

@api.post("/auth/logout")
async def logout(response: Response, user=Depends(current_user)):
    response.delete_cookie("access_token"); return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(current_user)): return user

@api.post("/auth/register")
async def register(data: UserCreate, user=Depends(admin_only)):
    if await db.users.find_one({"email": data.email.lower()}): raise HTTPException(400, "Email already exists")
    item = {"id": str(uuid.uuid4()), "name": data.name, "email": data.email.lower(), "phone": data.phone, "role": data.role, "active": True, "password_hash": hash_password(data.password), "created_at": now()}
    await db.users.insert_one(item); item.pop("password_hash"); return item

@api.get("/users")
async def users(user=Depends(admin_only)): return [safe(x) for x in await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("name", 1).to_list(100)]

@api.get("/sites")
async def sites(user=Depends(current_user)): return [safe(x) for x in await db.sites.find({}, {"_id": 0}).sort("site_name", 1).to_list(100)]
@api.post("/sites")
async def create_site(data: SiteCreate, user=Depends(admin_only)):
    item = {"id": str(uuid.uuid4()), **data.model_dump(), "active": True, "created_at": now()}; await db.sites.insert_one(item); return safe(item)
@api.get("/categories")
async def categories(user=Depends(current_user)): return [safe(x) for x in await db.categories.find({}, {"_id": 0}).sort("category_name", 1).to_list(100)]
@api.post("/categories")
async def create_category(data: SimpleCreate, user=Depends(admin_only)):
    item = {"id": str(uuid.uuid4()), "category_name": data.name, "active": True, "created_at": now()}; await db.categories.insert_one(item); return safe(item)

@api.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    txns = await db.transactions.find({}, {"_id": 0}).to_list(5000)
    sites = await db.sites.find({}, {"_id": 0}).to_list(100); cats = await db.categories.find({}, {"_id": 0}).to_list(100); employees = await db.users.find({"role": "employee"}, {"_id": 0}).to_list(100)
    site_names = {x["id"]: x["site_name"] for x in sites}; cat_names = {x["id"]: x["category_name"] for x in cats}
    def totals(key, labels): return [{"name": labels.get(k, "Unassigned"), "amount": round(sum(float(t.get("amount",0)) for t in txns if t.get(key)==k),2)} for k in labels]
    return {"summary": {"total": round(sum(float(t.get("amount",0)) for t in txns),2), "transactions": len(txns), "employees": len(employees), "sites": len(sites), "review": sum(t.get("classification_status")=="Needs Review" for t in txns), "duplicates": sum(t.get("duplicate_status")=="Possible Duplicate" for t in txns)}, "site_totals": totals("site_id", site_names), "category_totals": totals("category_id", cat_names), "recent": sorted(txns, key=lambda x:x.get("transaction_date", ""), reverse=True)[:8]}

@api.get("/transactions")
async def transactions(user=Depends(current_user)):
    return [safe(x) for x in await db.transactions.find({}, {"_id": 0}).sort("transaction_date", -1).to_list(5000)]
@api.patch("/transactions/{txn_id}")
async def update_transaction(txn_id: str, data: TransactionUpdate, user=Depends(current_user)):
    patch = {k:v for k,v in data.model_dump().items() if v is not None}; patch["classification_status"] = "Classified" if patch.get("site_id") and patch.get("category_id") else "Needs Review"
    result = await db.transactions.find_one_and_update({"id": txn_id}, {"$set": patch}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not result: raise HTTPException(404, "Transaction not found")
    return result

@api.post("/statements/upload")
async def upload_statement(employee_id: str = Form(...), statement_month: str = Form(...), statement_year: str = Form(...), file: UploadFile = File(...), user=Depends(current_user)):
    if user["role"] != "admin" and employee_id in {"", "undefined", "null"}: employee_id = user["id"]
    if user["role"] != "admin" and employee_id != user["id"]: raise HTTPException(403, "You can only upload your own statement")
    content = await file.read(); path = UPLOADS / f"{uuid.uuid4()}_{file.filename}"; path.write_bytes(content)
    try:
        df = pd.read_csv(io.BytesIO(content)) if file.filename.lower().endswith(".csv") else pd.read_excel(io.BytesIO(content))
    except Exception as exc: raise HTTPException(400, f"Could not read statement: {exc}")
    cols = {str(c).lower().strip(): c for c in df.columns}; date_col = next((cols[k] for k in cols if "date" in k), None); amount_col = next((cols[k] for k in cols if any(x in k for x in ["amount", "debit", "paid"])), None); desc_col = next((cols[k] for k in cols if any(x in k for x in ["description", "narration", "remark"])), None)
    if not date_col or not amount_col or not desc_col: raise HTTPException(400, "Could not detect date, amount, and description columns")
    sites = await db.sites.find({}, {"_id": 0}).to_list(100); cats = await db.categories.find({}, {"_id": 0}).to_list(100); rules = await db.classification_rules.find({"active": True}, {"_id": 0}).to_list(100)
    upload_id = str(uuid.uuid4()); records=[]; duplicate_count=0
    for _, row in df.iterrows():
        desc = str(row[desc_col]); amount = float(str(row[amount_col]).replace(",", "").replace("₹", "") or 0); date = str(row[date_col])[:10]; site_id=category_id=None
        for rule in sorted(rules, key=lambda r:r.get("priority",1)):
            if rule["keyword"].lower() in desc.lower(): site_id, category_id = rule["site_id"], rule["category_id"]; break
        duplicate = await db.transactions.find_one({"employee_id": employee_id, "transaction_date": date, "amount": amount, "description": desc}, {"_id": 0})
        if duplicate: duplicate_count += 1
        records.append({"id": str(uuid.uuid4()), "statement_upload_id": upload_id, "employee_id": employee_id, "transaction_date": date, "amount": amount, "transaction_type": "Debit", "description": desc, "site_id": site_id, "category_id": category_id, "classification_status": "Classified" if site_id and category_id else "Needs Review", "duplicate_status": "Possible Duplicate" if duplicate else "Clear", "created_at": now()})
    if records: await db.transactions.insert_many(records)
    statement = {"id": upload_id, "employee_id": employee_id, "statement_month": statement_month, "statement_year": statement_year, "original_file_name": file.filename, "file_path": str(path), "upload_date": now(), "total_transactions": len(records), "total_amount": sum(x["amount"] for x in records), "import_status": "Imported", "created_at": now()}; await db.statement_uploads.insert_one(statement)
    return {"id": upload_id, "imported": len(records), "total": statement["total_amount"], "classified": sum(x["classification_status"]=="Classified" for x in records), "review": sum(x["classification_status"]=="Needs Review" for x in records), "duplicates": duplicate_count}

@api.get("/statements")
async def statements(user=Depends(current_user)): return [safe(x) for x in await db.statement_uploads.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)]
@api.post("/seed")
async def seed(user=Depends(admin_only)): return await seed_data(force=True)

async def seed_data(force=False):
    if await db.users.find_one({"email": os.environ["ADMIN_EMAIL"]}): return {"seeded": False}
    admin={"id":str(uuid.uuid4()),"name":"Aarav Mehta","email":os.environ["ADMIN_EMAIL"],"phone":"","role":"admin","active":True,"password_hash":hash_password(os.environ["ADMIN_PASSWORD"]),"created_at":now()}; employee={"id":str(uuid.uuid4()),"name":"Rohan Kulkarni","email":"rohan@siteexpense.local","phone":"+91 98765 43210","role":"employee","active":True,"password_hash":hash_password("employee123"),"created_at":now()}; await db.users.insert_many([admin,employee])
    sites=[{"id":str(uuid.uuid4()),"site_name":"ABC Heights","site_code":"ABC-01","address":"Baner, Pune","active":True,"created_at":now()},{"id":str(uuid.uuid4()),"site_name":"XYZ Warehouse","site_code":"XYZ-02","address":"Wakad, Pune","active":True,"created_at":now()}]; cats=[{"id":str(uuid.uuid4()),"category_name":x,"active":True,"created_at":now()} for x in ["Cement","Diesel / Fuel","Labour","Material","Transport","Equipment","Food","Travel","Other"]]; await db.sites.insert_many(sites); await db.categories.insert_many(cats)
    for i,(site,cat,amount,desc) in enumerate([(sites[0],cats[0],18400,"ABC HEIGHTS CEMENT"),(sites[0],cats[1],9200,"ABC HEIGHTS DIESEL"),(sites[1],cats[2],27600,"XYZ WAREHOUSE LABOUR"),(sites[1],cats[3],12400,"XYZ WAREHOUSE MATERIAL"),(sites[0],cats[4],6800,"ABC HEIGHTS TRANSPORT")]): await db.transactions.insert_one({"id":str(uuid.uuid4()),"employee_id":employee["id"],"statement_upload_id":"sample","transaction_date":f"2026-08-{10+i}","amount":amount,"transaction_type":"Debit","description":desc,"site_id":site["id"],"category_id":cat["id"],"classification_status":"Classified","duplicate_status":"Clear","created_at":now()})
    return {"seeded": True}

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True); await seed_data()
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "https://site-spend-central.preview.emergentagent.com"], allow_methods=["*"], allow_headers=["*"])
@app.on_event("shutdown")
async def shutdown(): client.close()