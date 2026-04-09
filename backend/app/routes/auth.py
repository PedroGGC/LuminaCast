from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut, Token
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/auth", tags=["auth"])

from app.supabase_auth import get_current_user_supabase


@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    try:
        # Verifica se o usuário já existe
        existing_user = db.query(User).filter(User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email já cadastrado")

        # Hasheia a senha e cria o usuário
        hashed_pass = get_password_hash(user_in.senha)
        new_user = User(nome=user_in.nome, email=user_in.email, senha_hash=hashed_pass)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erro interno ao registrar usuário."
        )


from sqlalchemy import or_


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    identifier = form_data.username
    user = (
        db.query(User)
        .filter(or_(User.email == identifier, User.nome == identifier))
        .first()
    )

    if not user or not verify_password(form_data.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Informações incorretas. Verifique seu e-mail, nome de usuário ou senha.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


from app.auth import get_current_user
from app.schemas import UserBase
from pydantic import BaseModel


class UserUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's data."""
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's name and/or email."""
    if user_in.nome:
        current_user.nome = user_in.nome
    if user_in.email:
        # Verifica se o email é único
        existing = (
            db.query(User)
            .filter(User.email == user_in.email, User.id != current_user.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="E-mail já está em uso por outro usuário"
            )
        current_user.email = user_in.email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me-supabase")
async def get_me_supabase(user_data: dict = Depends(get_current_user_supabase)):
    """
    Retorna dados do usuário logado via Supabase JWT.
    Não gera token próprio - retorna apenas os dados do token validado.
    """
    return {"email": user_data["email"], "user_id": user_data["user_id"]}
