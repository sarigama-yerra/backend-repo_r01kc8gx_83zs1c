import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId
from passlib.context import CryptContext
from jose import jwt, JWTError

from database import db, create_document, get_documents
from schemas import Property, Offer, SiteSettings, AdminUser

# Auth settings
JWT_SECRET = os.getenv("JWT_SECRET", "devsecret")
JWT_ALG = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    token: str
    name: Optional[str] = None

# Utility to convert Mongo docs

def serialize_doc(doc):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
    doc.pop("_id", None)
    return doc

# Auth helpers

def create_token(payload: dict) -> str:
    to_encode = {**payload, "exp": datetime.now(timezone.utc).timestamp() + 60 * 60 * 8}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)

async def get_current_admin(token: str | None = None):
    # very simple token retrieval from header via FastAPI dependency would be better,
    # but keep minimal: clients pass token as query or header 'Authorization: Bearer <token>'
    from fastapi import Request
    request: Request = app.state.request  # not reliable; instead parse each route

# Public routes

@app.get("/")
async def root():
    return {"message": "Property Sale API running"}

@app.get("/schema")
async def schema():
    # expose schemas file classes by name for admin tooling
    return {"collections": ["adminuser", "sitesettings", "property", "offer"]}

# Properties CRUD

@app.get("/api/properties")
async def list_properties(featured: Optional[bool] = None):
    q = {}
    if featured is not None:
        q["featured"] = featured
    docs = get_documents("property", q)
    return [serialize_doc(d) for d in docs]

@app.post("/api/properties")
async def create_property(prop: Property):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    data = prop.model_dump()
    data["listed_at"] = datetime.now(timezone.utc)
    new_id = create_document("property", data)
    created = db["property"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(created)

@app.get("/api/properties/{property_id}")
async def get_property(property_id: str):
    doc = db["property"].find_one({"_id": ObjectId(property_id)})
    if not doc:
        raise HTTPException(404, "Property not found")
    return serialize_doc(doc)

@app.patch("/api/properties/{property_id}")
async def update_property(property_id: str, updates: dict):
    updates["updated_at"] = datetime.now(timezone.utc)
    res = db["property"].update_one({"_id": ObjectId(property_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Property not found")
    doc = db["property"].find_one({"_id": ObjectId(property_id)})
    return serialize_doc(doc)

@app.delete("/api/properties/{property_id}")
async def delete_property(property_id: str):
    res = db["property"].delete_one({"_id": ObjectId(property_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Property not found")
    return {"status": "ok"}

# Offers

@app.get("/api/offers")
async def list_offers(property_id: Optional[str] = None):
    q = {"property_id": property_id} if property_id else {}
    docs = get_documents("offer", q)
    return [serialize_doc(d) for d in docs]

@app.post("/api/offers")
async def create_offer(offer: Offer):
    new_id = create_document("offer", offer)
    created = db["offer"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(created)

@app.patch("/api/offers/{offer_id}")
async def update_offer(offer_id: str, updates: dict):
    updates["updated_at"] = datetime.now(timezone.utc)
    res = db["offer"].update_one({"_id": ObjectId(offer_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Offer not found")
    doc = db["offer"].find_one({"_id": ObjectId(offer_id)})
    return serialize_doc(doc)

# Site settings

@app.get("/api/settings")
async def get_settings():
    doc = db["sitesettings"].find_one({})
    if not doc:
        # default settings
        defaults = SiteSettings(site_name="Nova Estates", hero_headline="Find your next home", hero_subtitle="Browse curated properties", contact_email=None, phone=None)
        create_document("sitesettings", defaults)
        doc = db["sitesettings"].find_one({})
    return serialize_doc(doc)

@app.patch("/api/settings")
async def update_settings(updates: dict):
    updates["updated_at"] = datetime.now(timezone.utc)
    doc = db["sitesettings"].find_one({})
    if doc:
        db["sitesettings"].update_one({"_id": doc["_id"]}, {"$set": updates})
        doc = db["sitesettings"].find_one({})
    else:
        create_document("sitesettings", updates)
        doc = db["sitesettings"].find_one({})
    return serialize_doc(doc)

# Admin auth (basic email/password with JWT)

@app.post("/api/admin/seed")
async def seed_admin():
    # Idempotent seed: creates default admin if missing
    existing = db["adminuser"].find_one({"email": "admin@example.com"})
    if existing:
        return {"status": "exists"}
    password_hash = pwd_context.hash("admin123")
    admin = AdminUser(email="admin@example.com", password_hash=password_hash, name="Admin")
    create_document("adminuser", admin)
    return {"status": "created", "email": "admin@example.com", "password": "admin123"}

@app.post("/api/admin/login", response_model=LoginResponse)
async def admin_login(payload: LoginRequest):
    user = db["adminuser"].find_one({"email": payload.email})
    if not user:
        raise HTTPException(401, "Invalid credentials")
    if not pwd_context.verify(payload.password, user.get("password_hash")):
        raise HTTPException(401, "Invalid credentials")
    token = create_token({"sub": str(user.get("_id")), "email": user.get("email")})
    return LoginResponse(token=token, name=user.get("name"))

# Simple protected check using Authorization header
from fastapi import Request

@app.middleware("http")
async def add_request_to_state(request: Request, call_next):
    # make request available if needed
    response = await call_next(request)
    return response

@app.get("/test")
async def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
