import os
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError as JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from supabase import create_client, Client

from app.database import get_db
from app.models import User

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("ENV") == "production":
        raise RuntimeError("FATAL: SECRET_KEY is not set in production!")
    else:
        SECRET_KEY = "your-super-secret-key-luminacast"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Cliente Supabase para validação de tokens
supabase: Client = None


def get_supabase_client() -> Client:
    global supabase
    if supabase is None:
        supabase = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY")
        )
    return supabase


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
    """Valida token: tenta Supabase primeiro (Google), depois token próprio (email/senha)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = None
    nome = None

    # Tentativa 1: Token Supabase (Google OAuth)
    try:
        supabase_client = get_supabase_client()
        user_response = supabase_client.auth.get_user(token)

        if user_response and user_response.user:
            supabase_user = user_response.user
            email = supabase_user.email
            nome = (
                supabase_user.user_metadata.get("full_name")
                if supabase_user.user_metadata
                else None
            )

    except Exception:
        pass

    # Tentativa 2: Token próprio (email/password)
    if email is None:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
        except JWTError:
            pass

    if email is None:
        raise credentials_exception

    # Busca ou cria usuário no banco
    user = db.query(User).filter(User.email == email).first()

    if user is None:
        user = User(
            nome=nome or email.split("@")[0],
            email=email,
            senha_hash=get_password_hash(f"oauth_{email}"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[AUTH] Usuário criado: {email}")

    return user
