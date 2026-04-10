import os
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("ENV") == "production":
        raise RuntimeError("FATAL: SECRET_KEY is not set in production!")
    else:
        SECRET_KEY = "your-super-secret-key-luminacast"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias (access token expira em 7 dias)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """
    Suporta DOIS tipos de autenticação:
    1. Token próprio (email/password) - usa SECRET_KEY
    2. Token Supabase (Google OAuth) - usa SUPABASE_JWT_SECRET
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = None
    user_id = None

    # Tentativa 1: Token próprio (email/password)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user_id = payload.get("sub")
    except JWTError:
        pass

    # Tentativa 2: Token Supabase (Google OAuth)
    if email is None:
        supabase_secret = os.getenv("SUPABASE_JWT_SECRET")
        if supabase_secret:
            try:
                payload = jwt.decode(
                    token,
                    supabase_secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                email = payload.get("email")
                user_id = payload.get("sub")
            except JWTError:
                pass

    if email is None:
        raise credentials_exception

    # Busca usuário no banco (ou cria se for login Google primeira vez)
    user = db.query(User).filter(User.email == email).first()

    if user is None:
        from app.auth import get_password_hash

        user = User(
            nome=payload.get("user_metadata", {}).get("full_name", email.split("@")[0]),
            email=email,
            senha_hash=get_password_hash(f"google_oauth_{user_id}"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
