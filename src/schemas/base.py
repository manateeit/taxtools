from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, constr

class AccountReference(BaseModel):
    id: Optional[int] = None
    account_number: str
    company_name: str
    bank_name: str
    account_type: str
    created_at: Optional[date] = None
    updated_at: Optional[date] = None

class Transaction(BaseModel):
    date: date
    description: str
    amount: Decimal
    transaction_type: str = Field(..., pattern="^(deposit|withdrawal)$")
    tax_category: Optional[str] = None

class Statement(BaseModel):
    id: Optional[int] = None
    account_reference_id: int
    statement_date: date
    period_start: date
    period_end: date
    beginning_balance: Decimal
    ending_balance: Decimal
    total_fees: Decimal = Field(default=Decimal('0.00'))
    filename: str
    important_notes: Optional[str] = None
    created_at: Optional[date] = None
    updated_at: Optional[date] = None
    transactions: Optional[List[Transaction]] = None

class ProcessingResult(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    errors: Optional[List[str]] = None 