"""
Dependência de autenticação via Supabase JWT.
Valida token usando apenas SUPABASE_JWT_SECRET (validação stateless).
"""

import os
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
security = HTTPBearer()


async def get_current_user_supabase(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Valida JWT do Supabase usando apenas verificação criptográfica.
    NÃO consulta o banco do Supabase - apenas valida a assinatura.
    """
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET não configurada",
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )

        email = payload.get("email")
        user_id = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: email não encontrado",
            )

        return {"email": email, "user_id": user_id}

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token JWT inválido: {str(e)}",
        )
