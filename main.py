import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Place, Review, QuizResult

app = FastAPI(title="Women Travel Safety API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Helpers
# -------------------------

class IdModel(BaseModel):
    id: str


def objid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def serialize(doc: dict):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    # Convert any nested ObjectIds just in case
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


# -------------------------
# Basic + Schema Introspection
# -------------------------

@app.get("/")
def root():
    return {"message": "Women Travel Safety API running"}


@app.get("/schema")
def get_schema():
    # Minimal schema exposure for the client tools
    return {
        "collections": ["user", "place", "review", "quizresult"],
        "models": {
            "user": User.model_json_schema(),
            "place": Place.model_json_schema(),
            "review": Review.model_json_schema(),
            "quizresult": QuizResult.model_json_schema(),
        },
    }


@app.get("/test")
def test_database():
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
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# -------------------------
# Seed minimal sample data for demo
# -------------------------

@app.post("/seed")
def seed_sample():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    samples = [
        Place(
            name="Aurora Boutique Hotel",
            city="Lisbon",
            type="hotel",
            safety_score=4.7,
            description="Women-staffed, well-lit area; guests report safe returns at night.",
            main_tags=["women-staffed", "well-lit", "central"]
        ),
        Place(
            name="Garden District",
            city="Singapore",
            type="neighborhood",
            safety_score=4.9,
            description="Exceptionally safe at night; strong street presence and cameras.",
            main_tags=["night-safe", "family-friendly", "clean"]
        ),
        Place(
            name="Olive & Thyme",
            city="Barcelona",
            type="restaurant",
            safety_score=4.4,
            description="Busy staff presence, friendly crowd; avoid very late weekends.",
            main_tags=["staff-present", "friendly", "busy"]
        ),
    ]

    ids = []
    for p in samples:
        ids.append(create_document("place", p))
    return {"inserted": ids}


# -------------------------
# Places Directory
# -------------------------

@app.get("/places")
def list_places(city: Optional[str] = None, type: Optional[str] = None, q: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    filt = {}
    if city:
        filt["city"] = {"$regex": f"^{city}$", "$options": "i"}
    if type:
        filt["type"] = {"$regex": f"^{type}$", "$options": "i"}
    if q:
        filt["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"main_tags": {"$elemMatch": {"$regex": q, "$options": "i"}}},
        ]

    docs = get_documents("place", filt, None)
    return [serialize(d) for d in docs]


class NewReview(BaseModel):
    user_id: str
    rating: int = Field(..., ge=1, le=5)
    safety_tags: List[str] = []
    comment: Optional[str] = None
    night_safe: bool
    harassment: bool


@app.post("/places/{place_id}/reviews")
def add_review(place_id: str, payload: NewReview):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # ensure place exists
    place = db["place"].find_one({"_id": objid(place_id)})
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    review = Review(
        user_id=payload.user_id,
        place_id=place_id,
        rating=payload.rating,
        safety_tags=payload.safety_tags,
        comment=payload.comment,
        night_safe=payload.night_safe,
        harassment=payload.harassment,
    )
    rid = create_document("review", review)

    # naive safety score update (average of ratings)
    ratings = [r.get("rating", 0) for r in db["review"].find({"place_id": place_id})]
    if ratings:
        avg = sum(ratings) / len(ratings)
        db["place"].update_one({"_id": objid(place_id)}, {"$set": {"safety_score": round(avg, 2)}})

    return {"id": rid}


@app.get("/places/{place_id}/reviews")
def list_reviews(place_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    docs = list(db["review"].find({"place_id": place_id}).sort("created_at", -1))
    return [serialize(d) for d in docs]


# -------------------------
# Quiz Endpoint (lead magnet)
# -------------------------

class QuizAnswer(BaseModel):
    comfort_level: str
    solo_experience: str
    night_travel: str
    anxiety_triggers: List[str]
    transport_confidence: str


@app.post("/quiz")
def evaluate_quiz(ans: QuizAnswer, user_id: Optional[str] = None):
    # Simple scoring heuristic for MVP
    score = 0
    if ans.comfort_level in ["high", "medium"]:
        score += 2 if ans.comfort_level == "high" else 1
    if ans.solo_experience in ["5+", "2-4"]:
        score += 2 if ans.solo_experience == "5+" else 1
    if ans.night_travel == "comfortable":
        score += 2
    if "crowds" not in ans.anxiety_triggers:
        score += 1
    if ans.transport_confidence in ["metro", "ride-share"]:
        score += 1

    if score >= 6:
        persona = "Trailblazer"
        recs = ["Singapore", "Lisbon", "Copenhagen"]
    elif score >= 4:
        persona = "Planner"
        recs = ["Tokyo", "Vienna", "Seoul"]
    else:
        persona = "Cautious Explorer"
        recs = ["Reykjavik", "Zurich", "Taipei"]

    result = QuizResult(user_id=user_id, persona=persona, recommendations=recs, answers=ans.model_dump())
    rid = create_document("quizresult", result)

    return {"id": rid, "persona": persona, "recommendations": recs}


# -------------------------
# Auth-lite placeholders (email/google) + profile basics
# -------------------------

class Signup(BaseModel):
    name: str
    email: str
    photo: Optional[str] = None


@app.post("/auth/signup")
def signup(payload: Signup):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    existing = db["user"].find_one({"email": payload.email})
    if existing:
        return serialize(existing)

    uid = create_document("user", {"name": payload.name, "email": payload.email, "photo": payload.photo, "saved_places": [], "saved_cities": []})
    doc = db["user"].find_one({"_id": objid(uid)})
    return serialize(doc)


class SavePlace(BaseModel):
    place_id: str


@app.post("/me/{user_id}/save")
def save_place(user_id: str, payload: SavePlace):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    db["user"].update_one({"_id": objid(user_id)}, {"$addToSet": {"saved_places": payload.place_id}})
    doc = db["user"].find_one({"_id": objid(user_id)})
    return serialize(doc)


@app.get("/me/{user_id}")
def profile(user_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    doc = db["user"].find_one({"_id": objid(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize(doc)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
