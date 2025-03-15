from typing import List, Optional
from pydantic import BaseModel, Field, constr
from decimal import Decimal

class DepositTransaction(BaseModel):
    date: str = Field(..., pattern="^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(/\\d{4})?$")
    description: str = Field(..., pattern="^[a-zA-Z0-9\\s\\-\\:\\.\\#\\/\\(\\)\\,\\*\\_\\[\\]]+$")
    amount: float = Field(..., gt=0)

class WithdrawalTransaction(BaseModel):
    date: str = Field(..., pattern="^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])(/\\d{4})?$")
    description: str = Field(..., pattern="^[a-zA-Z0-9\\s\\-\\:\\.\\#\\/\\(\\)\\,\\*\\_\\[\\]]+$")
    amount: float = Field(..., gt=0)
    tax_category: str = Field(..., enum=[
        "Domestic Business Expense",
        "International Subcontractors",
        "Tax Payment",
        "Transfer",
        "Loan Payment",
        "Utility Payment",
        "Professional Services"
    ])

class StatementData(BaseModel):
    """Schema for parsed statement data."""
    account_number: str
    statement_date: str
    period_start: str
    period_end: str
    beginning_balance: Decimal
    ending_balance: Decimal
    total_fees: Decimal
    filename: str
    important_notes: str = ""
    deposits: List[DepositTransaction] = []
    withdrawals: List[WithdrawalTransaction] = []

class ErrorResponse(BaseModel):
    code: str = Field(..., enum=[
        "INVALID_ACCOUNT",
        "MISSING_STATEMENT_DATE",
        "MISSING_BALANCE",
        "MISSING_PERIOD_DATES",
        "PARSE_ERROR"
    ])
    message: str

class StatementResponse(BaseModel):
    status: str = Field(..., pattern="^(success|error)$")
    data: Optional[StatementData] = None
    error: Optional[ErrorResponse] = None 