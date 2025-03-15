import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Dict, List, Any

from src.config.settings import NEON_DB_URL

@contextmanager
def get_db_connection():
    """Create a database connection context manager."""
    conn = None
    try:
        conn = psycopg2.connect(NEON_DB_URL)
        yield conn
    finally:
        if conn is not None:
            conn.close()

@contextmanager
def get_db_cursor(commit=False):
    """Create a database cursor context manager."""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()

def fetch_account_reference(account_number: str) -> Dict[str, Any]:
    """Fetch account reference by account number."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM account_references 
            WHERE account_number = %s
            """,
            (account_number,)
        )
        return cursor.fetchone()

def fetch_all_accounts() -> List[Dict[str, Any]]:
    """Fetch all account references."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM account_references ORDER BY company_name, account_number")
        return cursor.fetchall()

def check_statement_exists(statement_filename: str) -> bool:
    """Check if a statement already exists in the database."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM banking_statements 
                        WHERE filename = %s
                    )
                    """,
                    (statement_filename,)
                )
                return cur.fetchone()[0]
    except Exception as e:
        print(f"Error checking statement existence: {e}")
        return False

def insert_statement(statement_data: Dict[str, Any]) -> int:
    """Insert a new statement and return its ID."""
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO banking_statements (
                account_reference_id, statement_date, period_start, period_end,
                beginning_balance, ending_balance, total_fees, filename,
                important_notes, raw_data
            ) VALUES (
                %(account_reference_id)s, %(statement_date)s, %(period_start)s,
                %(period_end)s, %(beginning_balance)s, %(ending_balance)s,
                %(total_fees)s, %(filename)s, %(important_notes)s, %(raw_data)s
            ) RETURNING id
            """,
            statement_data
        )
        result = cursor.fetchone()
        return result['id']

def insert_deposit(deposit_data: Dict[str, Any]) -> int:
    """Insert a new deposit transaction and return its ID."""
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO deposits (
                banking_statement_id, transaction_date, description, amount
            ) VALUES (
                %(banking_statement_id)s, %(transaction_date)s, %(description)s,
                %(amount)s
            ) RETURNING id
            """,
            deposit_data
        )
        result = cursor.fetchone()
        return result['id']

def insert_withdrawal(withdrawal_data: Dict[str, Any]) -> int:
    """Insert a new withdrawal transaction and return its ID."""
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO withdrawals (
                banking_statement_id, transaction_date, description, amount,
                tax_category
            ) VALUES (
                %(banking_statement_id)s, %(transaction_date)s, %(description)s,
                %(amount)s, %(tax_category)s
            ) RETURNING id
            """,
            withdrawal_data
        )
        result = cursor.fetchone()
        return result['id'] 