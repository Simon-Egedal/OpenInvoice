"""One-time account links and organization-scoped membership administration."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.auth import hash_password
from app.core.config import settings
from app.deliveries import enqueue_message
from app.models.entities import AccountToken, AuditLog, Organization, OrganizationMember, User


async def create_token(db, user, organization_id, purpose):
    raw = secrets.token_urlsafe(32)
    token = AccountToken(organization_id=organization_id, user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(), purpose=purpose, session_version=user.session_version or 0, expires_at=datetime.now(timezone.utc) + timedelta(hours=48 if purpose == "invitation" else 1))
    db.add(token); await db.flush()
    link = f"{settings.frontend_url.rstrip('/')}/auth/recover#{raw}"
    await enqueue_message(db, organization_id, user.email, purpose, f"{purpose}:{token.id}", {"token_id": str(token.id), "subject": "Your OpenInvoice invitation" if purpose == "invitation" else "Reset your OpenInvoice password", "body": f"Use this one-time link to set your password:\n{link}\n\nThis link expires in {'48 hours' if purpose == 'invitation' else '1 hour'}. If you did not request it, ignore this email."})
    return token


async def invite_account(db, payload, membership, actor):
    if settings.email_provider != "smtp":
        raise HTTPException(409, "Configure SMTP before inviting accounts")
    await db.scalar(select(Organization.id).where(Organization.id == membership.organization_id).with_for_update(key_share=True))
    email = str(payload.email).lower()
    existing = await db.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, full_name=email.split("@", 1)[0][:200], password_hash=hash_password(secrets.token_urlsafe(32)), is_active=False, session_version=0)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "An account with this email already exists") from None
    db.add(OrganizationMember(organization_id=membership.organization_id, user_id=user.id, role=payload.role, is_active=True))
    await create_token(db, user, membership.organization_id, "invitation")
    db.add(AuditLog(organization_id=membership.organization_id, user_id=actor.id, action="account.invited", entity_type="user", entity_id=user.id, new_values={"email": email, "role": payload.role}))
    await db.commit()
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": payload.role, "is_active": False, "membership_active": True, "invitation_pending": True}


async def request_reset(db, email):
    user = await db.scalar(select(User).where(func.lower(User.email) == str(email).lower()).with_for_update())
    if not user or not user.is_active or settings.email_provider != "smtp":
        return
    membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id, OrganizationMember.is_active == True).order_by(OrganizationMember.created_at))
    if not membership:
        return
    # Prevent repeated requests from creating an unbounded email queue.
    recent = await db.scalar(select(AccountToken.id).where(AccountToken.user_id == user.id, AccountToken.created_at > datetime.now(timezone.utc) - timedelta(minutes=2)))
    if recent:
        return
    await create_token(db, user, membership.organization_id, "reset")
    await db.commit()


async def consume_token(db, raw, password):
    digest = hashlib.sha256(raw.encode()).hexdigest()
    token = await db.scalar(select(AccountToken).where(AccountToken.token_hash == digest))
    if not token:
        raise HTTPException(400, "Link is invalid or expired")
    user = await db.scalar(select(User).where(User.id == token.user_id).with_for_update())
    await db.refresh(token)
    now = datetime.now(timezone.utc)
    if token.consumed_at or token.expires_at <= now or token.session_version != (user.session_version or 0):
        raise HTTPException(400, "Link is invalid or expired")
    membership = await db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id, OrganizationMember.organization_id == token.organization_id, OrganizationMember.is_active == True))
    if not membership or (token.purpose == "reset" and not user.is_active):
        raise HTTPException(400, "Link is invalid or expired")
    user.password_hash = hash_password(password)
    user.session_version = (user.session_version or 0) + 1
    if token.purpose == "invitation":
        user.is_active = True
    token.consumed_at = now
    db.add(AuditLog(organization_id=token.organization_id, user_id=user.id, action="account.password_set", entity_type="user", entity_id=user.id))
    await db.commit()


async def update_member(db, membership, actor, user_id, role=None, is_active=None, revoke=False):
    await db.scalar(select(Organization.id).where(Organization.id == membership.organization_id).with_for_update(key_share=True))
    target = await db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == membership.organization_id).with_for_update(key_share=True))
    if not target:
        raise HTTPException(404, "Account not found")
    if target.role == "owner" and (role is not None or is_active is not None):
        raise HTTPException(409, "The owner account cannot be disabled or have its role changed")
    if role is not None: target.role = role
    if is_active is not None: target.is_active = is_active
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    user.session_version = (user.session_version or 0) + 1
    if revoke and role is None and is_active is None:
        action = "account.sessions_revoked"
    else:
        action = "account.membership_updated"
    db.add(AuditLog(organization_id=membership.organization_id, user_id=actor.id, action=action, entity_type="user", entity_id=user_id, new_values={"role": target.role, "is_active": target.is_active}))
    await db.commit()
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": target.role, "is_active": target.is_active and user.is_active, "membership_active": target.is_active, "invitation_pending": not user.is_active}
