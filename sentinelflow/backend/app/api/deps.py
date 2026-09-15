from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.security import Principal, get_principal

DBSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
