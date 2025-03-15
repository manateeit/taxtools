import argparse
from pathlib import Path
from typing import Optional, List, Dict
import shutil
import json
from datetime import datetime

from src.agents.statement_ingestion_agent import StatementIngestionAgent
from src.utils.database import fetch_all_accounts, check_statement_exists
from src.utils.pdf import extract_text_from_pdf
from src.config.settings import FINANCIAL_STATEMENTS_DIR

def create_json_files(company: str, account_number: str, year: str, test_mode: bool = False) -> List[Dict]:
    """Create JSON files from PDFs without database ingestion.
    Returns list of results for further processing."""
    agent = StatementIngestionAgent()
    
    # Construct the paths
    base_dir = FINANCIAL_STATEMENTS_DIR / company / account_number / year
    pdf_dir = base_dir
    json_dir = base_dir / "json"
    processed_dir = base_dir / "processed"
    
    print(f"\nProcessing PDFs for:")
    print(f"Company:     {company}")
    print(f"Account:     {account_number}")
    print(f"Year:        {year}")
    print(f"Directory:   {pdf_dir}")
    
    # Create necessary directories
    json_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    if not pdf_dir.exists():
        print(f"\n❌ Error: Directory not found at: {pdf_dir}")
        return []
    
    # Process each PDF file
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"\n❌ Error: No PDF files found in: {pdf_dir}")
        return []
    
    if test_mode:
        print("\n🔍 Test mode: Processing only the first PDF file")
        pdf_files = pdf_files[:1]
    
    print(f"\nFound {len(pdf_files)} PDF files to process:")
    for pdf in pdf_files:
        print(f"- {pdf.name}")
    
    results = []
    for pdf_path in pdf_files:
        print(f"\nProcessing: {pdf_path.name}")
        print("-" * 50)
        
        try:
            # Extract text from PDF
            print("1. Extracting text from PDF...")
            text = extract_text_from_pdf(str(pdf_path))
            print("✓ Text extracted successfully")
            
            # Process statement to create JSON
            print("2. Processing text with AI model...")
            formatted_human_prompt = agent.human_prompt.format(filename=pdf_path.name, text=text)
            messages = [
                ("system", agent.system_prompt),
                ("human", formatted_human_prompt)
            ]
            
            try:
                response = agent.model.invoke(messages)
                print("✓ AI model processed successfully")
                
                print("3. Parsing AI response...")
                try:
                    content = response.content
                    # Handle response if it's wrapped in markdown code blocks
                    if content.startswith("```"):
                        # Remove markdown code blocks
                        content = content.replace("```json\n", "").replace("```\n", "").replace("```", "")
                    
                    data = json.loads(content)
                    if isinstance(data, dict) and 'data' in data:
                        data = data['data']
                    print("✓ Response parsed successfully")
                except json.JSONDecodeError as e:
                    print(f"❌ Error: Invalid JSON in AI response")
                    print(f"   Details: {str(e)}")
                    print(f"   Response content: {response.content[:200]}...")
                    raise
                
                # Extract month and year from statement_date
                print("4. Extracting date and saving JSON...")
                statement_date = data.get('statement_date', '')
                if statement_date:
                    date = datetime.strptime(statement_date, "%m/%d/%Y")
                    json_filename = f"{date.strftime('%m-%Y')}.json"
                else:
                    print("⚠️  Warning: No statement date found, using PDF filename")
                    json_filename = pdf_path.stem + ".json"
                
                # Save JSON file
                json_path = json_dir / json_filename
                with open(json_path, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"✓ Saved JSON to: {json_path}")
                
                # Move PDF to processed directory
                print("5. Moving PDF to processed directory...")
                processed_path = processed_dir / pdf_path.name
                shutil.move(str(pdf_path), str(processed_path))
                print(f"✓ Moved PDF to: {processed_path}")
                
                results.append({
                    "status": "success",
                    "filename": pdf_path.name,
                    "json_path": str(json_path),
                    "message": f"Successfully processed and saved to {json_filename}"
                })
                
            except Exception as e:
                error_msg = f"Failed to process PDF: {str(e)}"
                print(f"❌ Error: {error_msg}")
                results.append({
                    "status": "error",
                    "filename": pdf_path.name,
                    "message": error_msg
                })
                
        except Exception as e:
            error_msg = f"Failed to extract text: {str(e)}"
            print(f"❌ Error: {error_msg}")
            results.append({
                "status": "error",
                "filename": pdf_path.name,
                "message": error_msg
            })
    
    print("\nProcessing Summary:")
    print("=" * 50)
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"Total PDFs processed: {len(results)}")
    print(f"Successful:          {success_count}")
    print(f"Failed:              {error_count}")
    
    if results:
        print("\nDetailed Results:")
        print("-" * 50)
        for result in results:
            status_symbol = "✓" if result["status"] == "success" else "❌"
            print(f"{status_symbol} {result['filename']}")
            print(f"   {result['message']}")
    
    return results

def process_json_files(company: str, account_number: str, year: str, test_mode: bool = False) -> None:
    """Process JSON files for a specific company and account."""
    agent = StatementIngestionAgent()
    
    # Construct the path to JSON directory
    json_dir = FINANCIAL_STATEMENTS_DIR / company / account_number / year / "json"
    
    print(f"\nProcessing JSON files for:")
    print(f"Company:     {company}")
    print(f"Account:     {account_number}")
    print(f"Year:        {year}")
    print(f"Directory:   {json_dir}")
    
    if not json_dir.exists():
        print(f"\n❌ Error: JSON directory not found at: {json_dir}")
        return
    
    # Get all JSON files
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        print(f"\n❌ Error: No JSON files found in: {json_dir}")
        return
    
    if test_mode:
        print("\n🔍 Test mode: Processing only the first JSON file")
        json_files = json_files[:1]
    
    print(f"\nFound {len(json_files)} JSON files to process:")
    for json_file in json_files:
        print(f"- {json_file.name}")
    
    results = []
    for json_path in json_files:
        print(f"\nProcessing: {json_path.name}")
        print("-" * 50)
        
        try:
            # Read JSON file
            print("1. Reading JSON file...")
            try:
                with open(json_path) as f:
                    data = json.load(f)
                print("✓ JSON file read successfully")
            except json.JSONDecodeError as e:
                print(f"❌ Error: Invalid JSON in file")
                print(f"   Details: {str(e)}")
                raise
            
            # Check if already processed
            print("2. Checking if statement exists in database...")
            if check_statement_exists(data):
                print("⚠️  Statement already exists in database, skipping")
                results.append({
                    "status": "skipped",
                    "filename": json_path.name,
                    "message": "Statement already exists in database"
                })
                continue
            print("✓ Statement is new")
            
            # Process the JSON data
            print("3. Processing statement data...")
            agent._process_json_data(data)
            print("✓ Statement processed and added to database")
            
            results.append({
                "status": "success",
                "filename": json_path.name,
                "message": "Successfully processed and added to database"
            })
            
        except Exception as e:
            error_msg = f"Failed to process JSON: {str(e)}"
            print(f"❌ Error: {error_msg}")
            results.append({
                "status": "error",
                "filename": json_path.name,
                "message": error_msg
            })
    
    print("\nProcessing Summary:")
    print("=" * 50)
    success_count = sum(1 for r in results if r["status"] == "success")
    skip_count = sum(1 for r in results if r["status"] == "skipped")
    error_count = sum(1 for r in results if r["status"] == "error")
    print(f"Total JSON files:    {len(results)}")
    print(f"Successfully added:  {success_count}")
    print(f"Already in database: {skip_count}")
    print(f"Failed:              {error_count}")
    
    if results:
        print("\nDetailed Results:")
        print("-" * 50)
        for result in results:
            if result["status"] == "success":
                status_symbol = "✓"
            elif result["status"] == "skipped":
                status_symbol = "⚠️"
            else:
                status_symbol = "❌"
            print(f"{status_symbol} {result['filename']}")
            print(f"   {result['message']}")

def list_accounts() -> None:
    """List all available accounts."""
    accounts = fetch_all_accounts()
    
    if not accounts:
        print("\n⚠️  No accounts found in the database")
        return
    
    print("\nAvailable Accounts:")
    print("=" * 50)
    for account in accounts:
        print(f"Company: {account['company_name']}")
        print(f"Account: {account['account_number']}")
        print(f"Bank:    {account['bank_name']}")
        print(f"Type:    {account['account_type']}")
        print("-" * 50)

def complete_process(company: str, account_number: str, year: str, test_mode: bool = False) -> None:
    """Complete process: create JSON files and then process them."""
    print("\nStarting Complete Process")
    print("=" * 50)
    
    print("\nStep 1: Creating JSON Files")
    print("-" * 50)
    results = create_json_files(company, account_number, year, test_mode)
    
    if not results:
        print("\n❌ No files were processed in the create-json step")
        return
    
    success_count = sum(1 for r in results if r["status"] == "success")
    if success_count == 0:
        print("\n❌ No JSON files were successfully created, stopping process")
        return
    
    print("\nStep 2: Processing JSON Files")
    print("-" * 50)
    process_json_files(company, account_number, year, test_mode)

def main():
    parser = argparse.ArgumentParser(description="Bank Statement Processing CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Common arguments for commands that need them
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("company", help="Company name")
    common_parser.add_argument("account", help="Account number")
    common_parser.add_argument("year", help="Year")
    common_parser.add_argument("--test", action="store_true", help="Test mode - only process first file")
    
    # Create JSON command
    create_json_parser = subparsers.add_parser("create-json", 
                                             help="Create JSON files from PDFs",
                                             parents=[common_parser])
    
    # Process JSON command
    process_json_parser = subparsers.add_parser("process-json", 
                                              help="Process JSON files into database",
                                              parents=[common_parser])
    
    # Complete process command
    complete_parser = subparsers.add_parser("complete-process", 
                                          help="Create and process JSON files",
                                          parents=[common_parser])
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available accounts")
    
    args = parser.parse_args()
    
    if args.command == "create-json":
        create_json_files(args.company, args.account, args.year, args.test)
    elif args.command == "process-json":
        process_json_files(args.company, args.account, args.year, args.test)
    elif args.command == "complete-process":
        complete_process(args.company, args.account, args.year, args.test)
    elif args.command == "list":
        list_accounts()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 