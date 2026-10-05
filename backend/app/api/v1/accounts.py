from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.accounts import consume_token, request_reset, update_member, create_token
from app.auth import admin_membership, current_user, current_membership
from app.db.session import get_db
from app.schemas import AccountOut
from app.models.entities import User, OrganizationMember, Organization, AuditLog
from sqlalchemy import select

router = APIRouter()


class ResetIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=256)


class MemberUpdateIn(BaseModel):
    role: Literal["admin", "accountant", "approver", "member", "viewer"] | None = None
    is_active: bool | None = None
    revoke_sessions: bool = False


@router.post("/auth/reset-password", status_code=202)
async def reset_password(payload: ResetIn, db: AsyncSession=Depends(get_db)):
    await request_reset(db, payload.email)
    return {"message": "If this account can receive recovery email, a link will be sent."}


@router.post("/auth/consume-link", status_code=204)
async def accept_link(payload: TokenIn, request: Request, db: AsyncSession=Depends(get_db)):
    await consume_token(db, payload.token, payload.password)
    request.session.clear()
    return Response(status_code=204)


@router.post("/auth/revoke-sessions", status_code=204)
async def revoke_own_sessions(request: Request, user=Depends(current_user), m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    await db.refresh(user, with_for_update=True)
    user.session_version += 1
    db.add(AuditLog(organization_id=m.organization_id, user_id=user.id, action="account.sessions_revoked", entity_type="user", entity_id=user.id))
    await db.commit()
    request.session.clear()
    return Response(status_code=204)


@router.patch("/administration/accounts/{user_id}", response_model=AccountOut)
async def change_member(user_id: UUID, payload: MemberUpdateIn, user=Depends(current_user), m=Depends(admin_membership), db: AsyncSession=Depends(get_db)):
    return await update_member(db, m, user, user_id, payload.role, payload.is_active, payload.revoke_sessions)


@router.post("/administration/accounts/{user_id}/invite", status_code=202)
async def resend_invitation(user_id: UUID, m=Depends(admin_membership), db: AsyncSession=Depends(get_db)):
    from app.core.config import settings
    if settings.email_provider != "smtp":
        raise HTTPException(409, "Configure SMTP before inviting accounts")
    await db.scalar(select(Organization.id).where(Organization.id == m.organization_id).with_for_update(key_share=True))
    membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == m.organization_id, OrganizationMember.is_active == True))
    if not membership:
        raise HTTPException(404, "Account not found")
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user.is_active:
        raise HTTPException(409, "Account is already active; use password recovery")
    user.session_version += 1
    await create_token(db, user, m.organization_id, "invitation")
    db.add(AuditLog(organization_id=m.organization_id, action="account.invitation_renewed", entity_type="user", entity_id=user.id))
    await db.commit()
    return {"status": "queued"}
