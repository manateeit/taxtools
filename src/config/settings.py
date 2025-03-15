import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Database Configuration
NEON_DB_URL = os.getenv('NEON_DB_URL')

# Application Configuration
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Project Paths
BASE_DIR = Path(__file__).parent.parent.parent
PROMPTS_DIR = BASE_DIR / 'src' / 'prompts'
FINANCIAL_STATEMENTS_DIR = BASE_DIR / 'FinancialStatements'

# Model Configuration
DEFAULT_MODEL = "gpt-4-0125-preview"  # GPT-4.5
FALLBACK_MODEL = "gpt-3.5-turbo-0125"

# Validation Settings
VALID_ACCOUNT_TYPES = ['Business', 'Checking', 'Savings']
VALID_TAX_CATEGORIES = [
    'Domestic Business Expense',
    'International Subcontractors',
    'Tax Payment',
    'Transfer',
    'Loan Payment',
    'Utility Payment',
    'Professional Services'
] 