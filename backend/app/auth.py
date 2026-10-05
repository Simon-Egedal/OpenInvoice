from uuid import UUID
from fastapi import Depends, Header, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.entities import OrganizationMember, User

password_hash=PasswordHash.recommended()
def hash_password(password: str)->str: return password_hash.hash(password)
def verify_password(password: str, hashed: str)->bool: return password_hash.verify(password,hashed)

async def current_user(request: Request, db: AsyncSession=Depends(get_db))->User:
    raw=request.session.get("user_id")
    if not raw: raise HTTPException(401,"Authentication required")
    user=await db.get(User,UUID(raw))
    if not user or not user.is_active: raise HTTPException(401,"Authentication required")
    if request.session.get("session_version", 0) != (user.session_version or 0):
        request.session.clear()
        raise HTTPException(401, "Session revoked; sign in again")
    return user

async def current_membership(user: User=Depends(current_user), db: AsyncSession=Depends(get_db), x_organization_id: str|None=Header(default=None))->OrganizationMember:
    query=select(OrganizationMember).where(OrganizationMember.user_id==user.id, OrganizationMember.is_active == True)
    if x_organization_id:
        try: org_id=UUID(x_organization_id)
        except ValueError: raise HTTPException(400,"Invalid organization ID")
        query=query.where(OrganizationMember.organization_id==org_id)
    membership=(await db.execute(query.order_by(OrganizationMember.created_at))).scalars().first()
    if not membership: raise HTTPException(403,"No organization access")
    return membership

async def write_membership(membership: OrganizationMember=Depends(current_membership))->OrganizationMember:
    if membership.role not in {"owner", "admin", "accountant", "member"}:
        raise HTTPException(403,"Your organization role cannot make this change")
    return membership

async def admin_membership(membership: OrganizationMember=Depends(current_membership))->OrganizationMember:
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403,"Only organization administrators can access administration")
    return membership
