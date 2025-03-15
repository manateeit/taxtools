from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json
import re

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError

from src.config.settings import (
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    OPENAI_API_KEY,
    FINANCIAL_STATEMENTS_DIR
)
from src.utils.s3 import S3Client
from src.utils.pdf import extract_text_from_pdf
from src.utils.database import (
    fetch_account_reference,
    insert_statement,
    insert_deposit,
    insert_withdrawal,
    check_statement_exists
)
from src.schemas.statement_parser import (
    StatementResponse,
    StatementData,
    DepositTransaction,
    WithdrawalTransaction
)

class StatementIngestionAgent:
    def __init__(self):
        self.model = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=0,
            openai_api_key=OPENAI_API_KEY
        )
        self.fallback_model = ChatOpenAI(
            model=FALLBACK_MODEL,
            temperature=0,
            openai_api_key=OPENAI_API_KEY
        )
        self.s3_client = S3Client()
        self.response_parser = PydanticOutputParser(pydantic_object=StatementResponse)
        
        # Load prompts
        self.system_prompt = Path("src/prompts/statement_system_prompt.txt").read_text()
        self.human_prompt = Path("src/prompts/statement_human_prompt.txt").read_text()
        
        # Create prompt template with input variables
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", self.human_prompt)
        ]).partial()  # Make it partial to allow variable inputs

    def process_statement(self, filename: str, text: str) -> None:
        """Process a single bank statement."""
        # Format the human prompt with the actual filename and text
        formatted_human_prompt = self.human_prompt.format(filename=filename, text=text)
        
        # Create messages for the model
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=formatted_human_prompt)
        ]
        
        try:
            # Get response from OpenAI using LangChain's interface
            try:
                response = self.model.invoke(messages)
            except Exception as e:
                print(f"Primary model failed, falling back to {FALLBACK_MODEL}: {e}")
                response = self.fallback_model.invoke(messages)
            
            # Clean the response content - remove markdown code blocks if present
            content = response.content
            if content.startswith("```") and content.endswith("```"):
                # Extract content between code blocks
                content = re.sub(r'^```(?:json)?\n(.*)\n```$', r'\1', content.strip(), flags=re.DOTALL)
            
            # Parse the JSON response
            json_response = json.loads(content)
            
            # Extract the data portion if it's nested
            if isinstance(json_response, dict) and 'data' in json_response:
                data_content = json_response['data']
            else:
                data_content = json_response
            
            # Save the JSON to a file and get its path
            json_path = Path(self._save_json_response(filename, data_content))
            print(f"Saved JSON response to: {json_path}")
            
            # Process the JSON data and insert into database
            self._process_json_data(data_content)
            
            # Move the JSON file to its organized location
            try:
                # Get account number and reference
                account_number = data_content.get('account_number')
                if not account_number:
                    raise ValueError("Account number not found in JSON data")
                
                account_ref = fetch_account_reference(account_number)
                if not account_ref:
                    raise ValueError(f"Account not found: {account_number}")
                
                # Get year from statement date
                statement_date = data_content.get('statement_date')
                if not statement_date:
                    raise ValueError("Statement date not found in JSON data")
                year = statement_date.split('/')[-1]
                
                # Create the destination directory
                dest_dir = FINANCIAL_STATEMENTS_DIR / account_ref['company_name'] / account_number / year / "json"
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Move the file
                dest_path = dest_dir / json_path.name
                json_path.rename(dest_path)
                print(f"Moved processed file to: {dest_path}")
                
            except Exception as e:
                print(f"Warning: Could not move JSON file after processing: {e}")
                print(f"File remains in original location: {json_path}")
            
            print(f"Successfully processed and stored statement: {filename}")
            
        except ValidationError as e:
            print(f"Error validating response for {filename}: {str(e)}")
            print("Model response:", response.content if 'response' in locals() else "No response received")
            raise
        except Exception as e:
            print(f"Error processing statement {filename}: {str(e)}")
            print("Model response:", response.content if 'response' in locals() else "No response received")
            raise

    def _save_json_response(self, pdf_filename: str, data: dict) -> str:
        """Save the JSON response to a file."""
        # Extract last 4 digits, month, and year from filename
        match = re.search(r'(\d{4})-statements-(\d{4})-', pdf_filename)
        if match:
            year, last_four = match.groups()
            month = data.get('statement_date', '').split('/')[0]  # Get month from statement date
            json_filename = f"{last_four}{month}{year}.json"
        else:
            # Fallback to a default naming pattern if the filename doesn't match expected format
            json_filename = pdf_filename.replace('.pdf', '.json')
        
        # Create json directory if it doesn't exist
        json_dir = FINANCIAL_STATEMENTS_DIR / "json"
        json_dir.mkdir(exist_ok=True)
        
        # Save the JSON file
        json_path = json_dir / json_filename
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return str(json_path)

    def _process_json_data(self, data: dict) -> None:
        """Process JSON data and store it in the database."""
        try:
            # Get the year from statement date
            statement_year = data.get('statement_date', '').split('/')[-1]
            statement_month = data.get('statement_date', '').split('/')[0]
            
            # Format the filename as account-month-year.pdf
            if 'account_number' in data:
                last_four = data['account_number'][-4:]
                data['filename'] = f"{last_four}-{statement_month}-{statement_year}.pdf"
            
            # Append year to transaction dates if they don't have it
            if 'deposits' in data:
                for deposit in data['deposits']:
                    if '/' in deposit['date'] and len(deposit['date'].split('/')) == 2:
                        deposit['date'] = f"{deposit['date']}/{statement_year}"
            
            if 'withdrawals' in data:
                for withdrawal in data['withdrawals']:
                    if '/' in withdrawal['date'] and len(withdrawal['date'].split('/')) == 2:
                        withdrawal['date'] = f"{withdrawal['date']}/{statement_year}"
            
            try:
                # Parse the data directly with StatementData model
                parsed_data = StatementData(**data)
            except ValidationError as e:
                print("\nValidation error details:")
                for error in e.errors():
                    print(f"Field: {'.'.join(str(x) for x in error['loc'])}")
                    print(f"Error: {error['msg']}")
                    print(f"Type: {error['type']}\n")
                raise
            
            # Get account reference
            account_ref = fetch_account_reference(parsed_data.account_number)
            if not account_ref:
                raise ValueError(f"Account not found: {parsed_data.account_number}")
            
            # Prepare statement data
            statement_data = {
                'account_reference_id': account_ref['id'],
                'statement_date': datetime.strptime(parsed_data.statement_date, "%m/%d/%Y").date(),
                'period_start': datetime.strptime(parsed_data.period_start, "%m/%d/%Y").date(),
                'period_end': datetime.strptime(parsed_data.period_end, "%m/%d/%Y").date(),
                'beginning_balance': parsed_data.beginning_balance,
                'ending_balance': parsed_data.ending_balance,
                'total_fees': parsed_data.total_fees,
                'filename': parsed_data.filename,
                'important_notes': parsed_data.important_notes,
                'raw_data': json.dumps(data)
            }
            
            # Insert statement and get its ID
            statement_id = insert_statement(statement_data)
            
            # Insert deposits
            for deposit in parsed_data.deposits:
                deposit_data = {
                    'banking_statement_id': statement_id,
                    'transaction_date': datetime.strptime(deposit.date, "%m/%d/%Y").date(),
                    'description': deposit.description,
                    'amount': deposit.amount
                }
                insert_deposit(deposit_data)
            
            # Insert withdrawals
            for withdrawal in parsed_data.withdrawals:
                withdrawal_data = {
                    'banking_statement_id': statement_id,
                    'transaction_date': datetime.strptime(withdrawal.date, "%m/%d/%Y").date(),
                    'description': withdrawal.description,
                    'amount': withdrawal.amount,
                    'tax_category': withdrawal.tax_category
                }
                insert_withdrawal(withdrawal_data)
                
        except ValidationError as e:
            print(f"Validation error processing JSON data: {str(e)}")
            print("Data that failed validation:", json.dumps(data, indent=2))
            raise
        except Exception as e:
            print(f"Error processing JSON data: {str(e)}")
            raise

    def process_json_file(self, json_path: Path) -> None:
        """Process a single JSON file and store its data in the database."""
        try:
            # Read and parse the JSON file
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Process the JSON data and insert into database
            self._process_json_data(data)
            print(f"Successfully processed and stored data from: {json_path.name}")
            
            # Only move the file after successful database insertion
            try:
                # Get account number from the data
                account_number = data.get('account_number')
                if not account_number:
                    raise ValueError("Account number not found in JSON data")
                
                # Get account reference to find company name
                account_ref = fetch_account_reference(account_number)
                if not account_ref:
                    raise ValueError(f"Account not found: {account_number}")
                
                # Get year from statement date
                statement_date = data.get('statement_date')
                if not statement_date:
                    raise ValueError("Statement date not found in JSON data")
                year = statement_date.split('/')[-1]
                
                # Create the destination directory
                dest_dir = FINANCIAL_STATEMENTS_DIR / account_ref['company_name'] / account_number / year / "json"
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Move the file
                dest_path = dest_dir / json_path.name
                json_path.rename(dest_path)
                print(f"Moved processed file to: {dest_path}")
                
            except Exception as e:
                print(f"Warning: Could not move JSON file after processing: {e}")
                print(f"File remains in original location: {json_path}")
            
        except Exception as e:
            print(f"Error processing JSON file {json_path.name}: {str(e)}")
            raise

    def process_json_directory(self, json_dir: Path = None) -> List[Dict]:
        """Process all JSON files in the json directory."""
        if json_dir is None:
            json_dir = FINANCIAL_STATEMENTS_DIR / "json"
        
        results = []
        if not json_dir.exists():
            print(f"\nError: JSON directory not found: {json_dir}")
            return results
        
        json_files = list(json_dir.glob("*.json"))
        if not json_files:
            print(f"\nNo JSON files found in directory: {json_dir}")
            return results
        
        print(f"\nFound {len(json_files)} JSON files to process...")
        
        for json_file in json_files:
            print(f"\nProcessing {json_file.name}...")
            try:
                self.process_json_file(json_file)
                results.append({
                    "filename": json_file.name,
                    "status": "success",
                    "message": "Successfully processed and stored in database"
                })
            except Exception as e:
                results.append({
                    "filename": json_file.name,
                    "status": "error",
                    "message": str(e)
                })
        
        if results:
            print(f"\nProcessing complete. {len(results)} files processed.")
            
            # Count successful moves
            success_count = sum(1 for r in results if r["status"] == "success")
            if success_count > 0:
                print(f"\n{success_count} files were successfully processed and moved to their respective directories.")
            
            # Report any failures
            failures = [r for r in results if r["status"] == "error"]
            if failures:
                print(f"\n{len(failures)} files failed to process:")
                for failure in failures:
                    print(f"✗ {failure['filename']}: {failure['message']}")
        else:
            print("\nNo files were processed.")
        
        return results

    def process_directory(self, company: str, account_number: str, year: str, test_mode: bool = False) -> List[Dict]:
        """Process all statements in a specific directory."""
        results = []
        target_dir = FINANCIAL_STATEMENTS_DIR / company / account_number / year
        
        if not target_dir.exists():
            print(f"\nError: Directory not found: {target_dir}")
            print(f"Please ensure statements are placed in the correct directory structure:")
            print(f"FinancialStatements/[Company Name]/[Account Number]/[Year]/")
            return results
            
        pdf_files = list(target_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"\nNo PDF files found in directory: {target_dir}")
            print(f"Please ensure your bank statements are:")
            print(f"1. In PDF format")
            print(f"2. Located in the correct directory")
            print(f"3. Have a .pdf extension")
            return results
        
        if test_mode:
            print(f"\nTest mode: Will only process the first PDF file")
            pdf_files = pdf_files[:1]
        else:
            print(f"\nFound {len(pdf_files)} PDF files to process...")
        
        for pdf_file in pdf_files:
            print(f"\nChecking {pdf_file.name}...")
            
            # First check if it's already in the database
            if check_statement_exists(pdf_file.name):
                print(f"Statement {pdf_file.name} already exists in database, skipping...")
                continue
            
            # Extract the month and last 4 digits from filename
            match = re.search(r'(\d{8})-statements-(\d{4})-', pdf_file.name)
            if match:
                date_str, last_four = match.groups()
                year = date_str[:4]
                month = date_str[4:6]
            else:
                # Try alternative pattern
                match = re.search(r'(\d{4})(\d{2})\d{2}-statements-(\d{4})-', pdf_file.name)
                if match:
                    year, month, last_four = match.groups()
                else:
                    print(f"Could not extract date and identifier from filename: {pdf_file.name}")
                    continue
            
            # Check if JSON already exists in the organized directory structure
            json_pattern = f"{last_four}{month}{year}.json"  # Exact pattern match
            organized_json_dir = FINANCIAL_STATEMENTS_DIR / company / account_number / year / "json"
            temp_json_dir = FINANCIAL_STATEMENTS_DIR / "json"
            
            # Check both in organized directory and temporary json directory
            existing_json = []
            if organized_json_dir.exists():
                exact_match = organized_json_dir / json_pattern
                if exact_match.exists():
                    existing_json.append(exact_match)
            
            if not existing_json and temp_json_dir.exists():
                exact_match = temp_json_dir / json_pattern
                if exact_match.exists():
                    existing_json.append(exact_match)
            
            if existing_json:
                print(f"Statement {pdf_file.name} has already been processed to JSON (found {existing_json[0].name}), skipping...")
                continue
            
            print(f"Processing {pdf_file.name}...")
            text_content = extract_text_from_pdf(pdf_file)
            if not text_content:
                results.append({
                    "filename": pdf_file.name,
                    "status": "error",
                    "message": "Could not extract text from the PDF"
                })
                continue
            
            try:
                # Process the PDF and create JSON
                self.process_statement(pdf_file.name, text_content)
                results.append({
                    "filename": pdf_file.name,
                    "status": "success",
                    "message": "Successfully processed and stored in database"
                })
            except Exception as e:
                results.append({
                    "filename": pdf_file.name,
                    "status": "error",
                    "message": str(e)
                })
        
        if results:
            print(f"\nProcessing complete. {len(results)} new files processed.")
            
            # Count successful moves
            success_count = sum(1 for r in results if r["status"] == "success")
            if success_count > 0:
                print(f"\n{success_count} files were successfully processed and moved to their respective directories.")
            
            # Report any failures
            failures = [r for r in results if r["status"] == "error"]
            if failures:
                print(f"\n{len(failures)} files failed to process:")
                for failure in failures:
                    print(f"✗ {failure['filename']}: {failure['message']}")
        else:
            print("\nNo new files were processed.")
        
        return results

    def _store_statement_data(self, data: StatementData) -> None:
        """Store the processed statement data in the database."""
        try:
            # Get account reference
            account_ref = fetch_account_reference(data.account_number)
            if not account_ref:
                raise ValueError(f"Account not found: {data.account_number}")

            # Insert statement
            statement_data = {
                "account_reference_id": account_ref["id"],
                "statement_date": datetime.strptime(data.statement_date, "%m/%d/%Y").date(),
                "period_start": datetime.strptime(data.period_start, "%m/%d/%Y").date(),
                "period_end": datetime.strptime(data.period_end, "%m/%d/%Y").date(),
                "beginning_balance": data.beginning_balance,
                "ending_balance": data.ending_balance,
                "total_fees": data.total_fees,
                "filename": data.filename,
                "important_notes": data.important_notes,
                "raw_data": json.dumps(data.dict())
            }
            
            statement_id = insert_statement(statement_data)
            
            # Insert deposits
            for deposit in data.deposits:
                deposit_data = {
                    "banking_statement_id": statement_id,
                    "transaction_date": datetime.strptime(deposit.date, "%m/%d/%Y").date(),
                    "description": deposit.description,
                    "amount": deposit.amount
                }
                insert_deposit(deposit_data)
            
            # Insert withdrawals
            for withdrawal in data.withdrawals:
                withdrawal_data = {
                    "banking_statement_id": statement_id,
                    "transaction_date": datetime.strptime(withdrawal.date, "%m/%d/%Y").date(),
                    "description": withdrawal.description,
                    "amount": withdrawal.amount,
                    "tax_category": withdrawal.tax_category
                }
                insert_withdrawal(withdrawal_data)
                
        except Exception as e:
            print(f"Error storing statement data: {e}")
            raise 