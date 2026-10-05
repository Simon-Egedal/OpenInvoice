from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.entities import InvoiceStatus, InvoiceType, MemberRole

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class RegisterIn(BaseModel): email: EmailStr; password: str=Field(min_length=12); full_name: str=Field(min_length=1,max_length=200); organization_name: str=Field(min_length=1,max_length=200)
class LoginIn(BaseModel): email: EmailStr; password: str
class SetupIn(BaseModel):
    database_mode: Literal["bundled", "external"] = "bundled"
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "openinvoice"
    database_username: str = "openinvoice"
    database_password: str = ""
    database_ssl: bool = False
    email_provider: Literal["console", "smtp"] = "console"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    storage_provider: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "eu-central-1"
    banking_provider: Literal["mock", "enable_banking"] = "mock"
    enable_banking_app_id: str = ""
    enable_banking_private_key_path: str = ""
    session_cookie_secure: bool = False

    @field_validator("database_host", "database_name", "database_username", "smtp_host", "smtp_from", "s3_bucket", "s3_region", mode="before")
    @classmethod
    def strip_configuration_text(cls, value):
        return value.strip() if isinstance(value, str) else value
class InfrastructureSettingsIn(SetupIn):
    pass
class InfrastructureSettingsOut(BaseModel):
    can_manage: bool = True
    database_mode: str = "bundled"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "openinvoice"
    database_username: str = "openinvoice"
    database_ssl: bool = False
    has_database_password: bool = False
    email_provider: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    has_smtp_password: bool = False
    storage_provider: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_region: str = "eu-central-1"
    has_s3_secret: bool = False
    banking_provider: str = "mock"
    enable_banking_app_id: str = ""
    enable_banking_private_key_path: str = ""
    session_cookie_secure: bool = False
    restart_required: bool = False
class UserOut(ORMModel): id: UUID; email: EmailStr; full_name: str
class CurrentUserOut(UserOut):
    role: MemberRole

class AccountCreateIn(BaseModel):
    email: EmailStr
    role: Literal["member", "admin"]

class AccountOut(UserOut):
    role: MemberRole

class ProfileUpdateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=256)

class OrganizationOut(ORMModel):
    id: UUID
    name: str
    country: str
    currency: str
    logo_key: str | None = None
    logo_url: str | None = None

class OrganizationUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(default="DK", min_length=2, max_length=2)
    currency: str = Field(default="DKK", min_length=1, max_length=10)

    @field_validator("name", "country", "currency", mode="before")
    @classmethod
    def clean_strings(cls, value):
        return value.strip() if isinstance(value, str) else value

class SetupAdminIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=12)
    organization_id: UUID | None = None
class SetupOrgOut(ORMModel):
    id: UUID
    name: str
    country: str
    currency: str
    logo_key: str | None = None
    logo_url: str | None = None
class CustomerIn(BaseModel):
    name: str
    email: EmailStr|None=None
    phone: str|None=None
    address: str|None=None
    postal_code: str|None=None
    city: str|None=None
    country: str="DK"
    vat_number: str|None=None
    payment_information: str|None=None
    notes: str|None=None

    @field_validator("email", "phone", "address", "postal_code", "city", "vat_number", "payment_information", "notes", mode="before")
    @classmethod
    def empty_optional_strings_are_null(cls, value): return None if value == "" else value
class CustomerOut(ORMModel): id: UUID; name: str; email: str|None; phone: str|None; address: str|None; postal_code: str|None; city: str|None; country: str; vat_number: str|None; payment_information: str|None; notes: str|None
SupplierIn=CustomerIn
SupplierOut=CustomerOut
class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)

    @field_validator("name", mode="before")
    @classmethod
    def clean_product_name(cls, value):
        return value.strip() if isinstance(value, str) else value

class ProductOut(ORMModel): id: UUID; name: str; unit_price: Decimal
class InvoiceLineIn(BaseModel): description: str=Field(min_length=1,max_length=500); quantity: Decimal=Field(gt=0); unit_price: Decimal=Field(ge=0); tax_rate: Decimal=Field(ge=0,le=100)
class InvoiceIn(BaseModel): invoice_number: str; invoice_type: InvoiceType=InvoiceType.outgoing; customer_id: UUID|None=None; supplier_id: UUID|None=None; issue_date: date; due_date: date; currency: str="DKK"; notes: str|None=None; lines: list[InvoiceLineIn]=Field(min_length=1)
class InvoiceLineOut(ORMModel): id: UUID; description: str; quantity: Decimal; unit_price: Decimal; tax_rate: Decimal; line_total: Decimal
class InvoiceOut(ORMModel):
    id: UUID
    organization_id: UUID
    organization_name: str | None = None
    organization_logo_url: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    recipient_phone: str | None = None
    recipient_address: str | None = None
    recipient_postal_code: str | None = None
    recipient_city: str | None = None
    recipient_country: str | None = None
    recipient_vat_number: str | None = None
    recipient: CustomerOut | None = None
    invoice_number: str
    invoice_type: InvoiceType
    status: InvoiceStatus
    customer_id: UUID | None
    supplier_id: UUID | None
    issue_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    paid_amount: Decimal = Decimal("0.00")
    due_amount: Decimal = Decimal("0.00")
    notes: str | None
    created_at: datetime

class ManualPaymentIn(BaseModel):
    amount: Decimal | None = None
    payment_date: date | None = None
    payment_method: str = "manual"
    reference: str | None = None
    notes: str | None = None

class InvoicePaymentOut(ORMModel):
    id: UUID
    invoice_id: UUID
    amount: Decimal
    payment_date: date
    payment_method: str
    reference: str | None
    notes: str | None
    created_at: datetime

class LinkTransactionIn(BaseModel):
    transaction_id: UUID
    amount: Decimal | None = None

class LinkInvoiceIn(BaseModel):
    invoice_id: UUID
    amount: Decimal | None = None

class InvoiceMatchOut(ORMModel):
    id: UUID
    invoice_id: UUID
    transaction_id: UUID
    amount: Decimal
    confidence: Decimal
    confirmed: bool
    created_at: datetime
    transaction_booked_at: datetime | None = None
    transaction_description: str | None = None
    transaction_counterparty: str | None = None
    transaction_amount: Decimal | None = None
    transaction_currency: str | None = None
    transaction_reference: str | None = None

class MatchedInvoiceSummary(BaseModel):
    match_id: UUID
    invoice_id: UUID
    invoice_number: str
    amount: Decimal
    invoice_total: Decimal
    invoice_status: str

class BankTransactionDetailOut(BaseModel):
    id: str
    booked_at: str
    description: str
    counterparty: str
    amount: str
    currency: str
    reference: str | None
    matched_amount: str = "0.00"
    unmatched_amount: str = "0.00"
    matches: list[MatchedInvoiceSummary] = []

class LinkableTransactionOut(BaseModel):
    id: UUID
    booked_at: datetime
    description: str
    counterparty: str | None
    amount: Decimal
    currency: str
    reference: str | None
    matched_amount: Decimal
    available_amount: Decimal

class BankAuthorizeIn(BaseModel):
    aspsp_name: str | None = None
    aspsp_country: str | None = None
class BankCallbackIn(BaseModel):
    code: str

