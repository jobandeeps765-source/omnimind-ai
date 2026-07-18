from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId

from app.auth.models import SignupRequest, LoginRequest, TokenResponse, UserOut
from app.auth.utils import hash_password, verify_password, create_access_token, get_current_user
from app.db.mongo import users_collection

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest):
    existing = await users_collection().find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    doc = {
        "email": body.email,
        "name": body.name,
        "password_hash": hash_password(body.password),
        "preferences": {},
    }
    result = await users_collection().insert_one(doc)
    token = create_access_token(str(result.inserted_id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = await users_collection().find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(str(user["_id"]))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(
        id=str(user["_id"]),
        email=user["email"],
        name=user["name"],
        preferences=user.get("preferences", {}),
    )
