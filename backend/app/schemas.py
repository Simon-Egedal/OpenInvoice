from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.entities import InvoiceStatus, InvoiceType, MemberRole

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class RegisterIn(BaseModel): email: EmailStr; password: str=Field(min_length=12); full_name: str=Field(min_length=1,max_length=200); organization_name: str=Field(min_length=1,max_length=200)
class LoginIn(BaseModel): email: EmailStr; password: str
class UserOut(ORMModel): id: UUID; email: EmailStr; full_name: str
class OrganizationOut(ORMModel): id: UUID; name: str; country: str; currency: str
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
class InvoiceLineIn(BaseModel): description: str=Field(min_length=1,max_length=500); quantity: Decimal=Field(gt=0); unit_price: Decimal=Field(ge=0); tax_rate: Decimal=Field(ge=0,le=100)
class InvoiceIn(BaseModel): invoice_number: str; invoice_type: InvoiceType=InvoiceType.outgoing; customer_id: UUID|None=None; supplier_id: UUID|None=None; issue_date: date; due_date: date; currency: str="DKK"; notes: str|None=None; lines: list[InvoiceLineIn]=Field(min_length=1)
class InvoiceLineOut(ORMModel): id: UUID; description: str; quantity: Decimal; unit_price: Decimal; tax_rate: Decimal; line_total: Decimal
class InvoiceOut(ORMModel): id: UUID; invoice_number: str; invoice_type: InvoiceType; status: InvoiceStatus; customer_id: UUID|None; supplier_id: UUID|None; issue_date: date; due_date: date; currency: str; subtotal: Decimal; tax_amount: Decimal; total: Decimal; notes: str|None; created_at: datetime
