import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

def now_utc(): return datetime.now(timezone.utc)
class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

class MemberRole(str, enum.Enum):
    owner="owner"; admin="admin"; accountant="accountant"; approver="approver"; member="member"; viewer="viewer"
class InvoiceType(str, enum.Enum): incoming="incoming"; outgoing="outgoing"
class InvoiceStatus(str, enum.Enum):
    draft="draft"; received="received"; pending_approval="pending_approval"; approved="approved"; sent="sent"; partially_paid="partially_paid"; paid="paid"; overdue="overdue"; cancelled="cancelled"; rejected="rejected"

class User(IdMixin, TimestampMixin, Base):
    __tablename__="users"
    email: Mapped[str]=mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    full_name: Mapped[str]=mapped_column(String(200))
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)

class Organization(IdMixin, TimestampMixin, Base):
    __tablename__="organizations"
    name: Mapped[str]=mapped_column(String(200))
    country: Mapped[str]=mapped_column(String(2), default="DK")
    currency: Mapped[str]=mapped_column(String(3), default="DKK")
    logo_key: Mapped[str|None]=mapped_column(String(500), nullable=True)

class OrganizationMember(IdMixin, TimestampMixin, Base):
    __tablename__="organization_members"
    __table_args__=(UniqueConstraint("organization_id","user_id"),)
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MemberRole]=mapped_column(Enum(MemberRole, name="member_role"), default=MemberRole.member)

class Party(IdMixin, TimestampMixin, Base):
    __abstract__=True
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]=mapped_column(String(200), index=True)
    email: Mapped[str|None]=mapped_column(String(320), nullable=True)
    phone: Mapped[str|None]=mapped_column(String(50), nullable=True)
    address: Mapped[str|None]=mapped_column(String(300), nullable=True)
    postal_code: Mapped[str|None]=mapped_column(String(30), nullable=True)
    city: Mapped[str|None]=mapped_column(String(100), nullable=True)
    country: Mapped[str]=mapped_column(String(2), default="DK")
    vat_number: Mapped[str|None]=mapped_column(String(80), nullable=True)
    payment_information: Mapped[str|None]=mapped_column(Text, nullable=True)
    notes: Mapped[str|None]=mapped_column(Text, nullable=True)
class Customer(Party): __tablename__="customers"
class Supplier(Party): __tablename__="suppliers"

class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__="invoices"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    supplier_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    invoice_number: Mapped[str]=mapped_column(String(100))
    invoice_type: Mapped[InvoiceType]=mapped_column(Enum(InvoiceType, name="invoice_type"))
    status: Mapped[InvoiceStatus]=mapped_column(Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.draft, index=True)
    issue_date: Mapped[datetime.date]=mapped_column(Date)
    due_date: Mapped[datetime.date]=mapped_column(Date)
    currency: Mapped[str]=mapped_column(String(3), default="DKK")
    subtotal: Mapped[Decimal]=mapped_column(Numeric(14,2), default=Decimal("0"))
    tax_amount: Mapped[Decimal]=mapped_column(Numeric(14,2), default=Decimal("0"))
    total: Mapped[Decimal]=mapped_column(Numeric(14,2), default=Decimal("0"))
    notes: Mapped[str|None]=mapped_column(Text, nullable=True)

class InvoiceLine(IdMixin, Base):
    __tablename__="invoice_lines"
    invoice_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    description: Mapped[str]=mapped_column(String(500))
    quantity: Mapped[Decimal]=mapped_column(Numeric(12,3))
    unit_price: Mapped[Decimal]=mapped_column(Numeric(14,2))
    tax_rate: Mapped[Decimal]=mapped_column(Numeric(6,3), default=Decimal("0"))
    line_total: Mapped[Decimal]=mapped_column(Numeric(14,2))

class InvoiceDocument(IdMixin, TimestampMixin, Base):
    __tablename__="invoice_documents"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str]=mapped_column(String(500))
    original_filename: Mapped[str]=mapped_column(String(255))
    content_type: Mapped[str]=mapped_column(String(100))
    size_bytes: Mapped[int]=mapped_column(Integer)

class BankConnection(IdMixin, TimestampMixin, Base):
    __tablename__="bank_connections"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str]=mapped_column(String(80))
    provider_reference: Mapped[str|None]=mapped_column(String(200), nullable=True)
    status: Mapped[str]=mapped_column(String(30), default="connected")
    last_synced_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
class BankAccount(IdMixin, TimestampMixin, Base):
    __tablename__="bank_accounts"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True), ForeignKey("bank_connections.id", ondelete="CASCADE"), nullable=True)
    provider_account_id: Mapped[str]=mapped_column(String(200))
    name: Mapped[str]=mapped_column(String(150))
    bank_name: Mapped[str]=mapped_column(String(150))
    masked_number: Mapped[str]=mapped_column(String(40))
    currency: Mapped[str]=mapped_column(String(3), default="DKK")
    balance: Mapped[Decimal]=mapped_column(Numeric(16,2), default=Decimal("0"))
    last_synced_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
class BankTransaction(IdMixin, TimestampMixin, Base):
    __tablename__="bank_transactions"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="CASCADE"), index=True)
    provider_transaction_id: Mapped[str]=mapped_column(String(200))
    booked_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    description: Mapped[str]=mapped_column(String(300))
    counterparty: Mapped[str|None]=mapped_column(String(200), nullable=True)
    amount: Mapped[Decimal]=mapped_column(Numeric(16,2))
    currency: Mapped[str]=mapped_column(String(3), default="DKK")
    reference: Mapped[str|None]=mapped_column(String(200), nullable=True)
class InvoiceTransactionMatch(IdMixin, TimestampMixin, Base):
    __tablename__="invoice_transaction_matches"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"))
    transaction_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("bank_transactions.id", ondelete="CASCADE"))
    confidence: Mapped[Decimal]=mapped_column(Numeric(5,2))
    confirmed: Mapped[bool]=mapped_column(Boolean, default=False)
class EmailDelivery(IdMixin, TimestampMixin, Base):
    __tablename__="email_deliveries"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"))
    recipient: Mapped[str]=mapped_column(String(320))
    status: Mapped[str]=mapped_column(String(30), default="queued")
    failed_attempts: Mapped[int]=mapped_column(Integer, default=0)
    error_message: Mapped[str|None]=mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str|None]=mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
class AuditLog(IdMixin, Base):
    __tablename__="audit_logs"
    organization_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str]=mapped_column(String(100), index=True)
    entity_type: Mapped[str]=mapped_column(String(100))
    entity_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True))
    old_values: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    new_values: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

