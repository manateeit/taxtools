# Statement Ingestion Output Parser

## Success Response Schema
```json
{
  "type": "object",
  "required": [
    "status",
    "data"
  ],
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success"]
    },
    "data": {
      "type": "object",
      "required": [
        "statement_filename",
        "account_number",
        "statement_date",
        "period_start",
        "period_end",
        "beginning_balance",
        "ending_balance",
        "total_fees",
        "important_notes",
        "deposits",
        "withdrawals"
      ],
      "properties": {
        "statement_filename": {
          "type": "string",
          "pattern": "^[^/]+\\.pdf$"
        },
        "account_number": {
          "type": "string",
          "enum": [
            "000000228239080",
            "000000954291944",
            "000000333721212",
            "00085695149",
            "000000880865188"
          ]
        },
        "statement_date": {
          "type": "string",
          "pattern": "^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])/\\d{4}$"
        },
        "period_start": {
          "type": "string",
          "pattern": "^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])/\\d{4}$"
        },
        "period_end": {
          "type": "string",
          "pattern": "^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])/\\d{4}$"
        },
        "beginning_balance": {
          "type": "number",
          "minimum": 0
        },
        "ending_balance": {
          "type": "number",
          "minimum": 0
        },
        "total_fees": {
          "type": "number",
          "minimum": 0
        },
        "important_notes": {
          "type": "string",
          "pattern": "^[a-zA-Z0-9\\s]*$"
        },
        "deposits": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["date", "description", "amount"],
            "properties": {
              "date": {
                "type": "string",
                "pattern": "^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])/\\d{4}$"
              },
              "description": {
                "type": "string",
                "pattern": "^[a-zA-Z0-9\\s]*$"
              },
              "amount": {
                "type": "number",
                "minimum": 0
              }
            }
          }
        },
        "withdrawals": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["date", "description", "amount", "tax_category"],
            "properties": {
              "date": {
                "type": "string",
                "pattern": "^(0[1-9]|1[0-2])/(0[1-9]|[12]\\d|3[01])/\\d{4}$"
              },
              "description": {
                "type": "string",
                "pattern": "^[a-zA-Z0-9\\s]*$"
              },
              "amount": {
                "type": "number",
                "minimum": 0
              },
              "tax_category": {
                "type": "string",
                "enum": [
                  "Domestic Business Expense",
                  "International Subcontractors",
                  "Tax Payment",
                  "Transfer",
                  "Loan Payment",
                  "Utility Payment",
                  "Professional Services"
                ]
              }
            }
          }
        }
      }
    }
  }
}
```

## Error Response Schema
```json
{
  "type": "object",
  "required": [
    "status",
    "error"
  ],
  "properties": {
    "status": {
      "type": "string",
      "enum": ["error"]
    },
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "INVALID_ACCOUNT",
            "MISSING_STATEMENT_DATE",
            "MISSING_BALANCE",
            "MISSING_PERIOD_DATES",
            "PARSE_ERROR"
          ]
        },
        "message": {
          "type": "string"
        }
      }
    }
  }
}
```

## Example Success Response
```json
{
  "status": "success",
  "data": {
    "statement_filename": "statement_2023_01.pdf",
    "account_number": "000000954291944",
    "statement_date": "01/31/2023",
    "period_start": "12/31/2022",
    "period_end": "01/31/2023",
    "beginning_balance": 4752.54,
    "ending_balance": 2581.22,
    "total_fees": 0.00,
    "important_notes": "Were changing how we charge fees for ACH Payment Services",
    "deposits": [
      {
        "date": "01/03/2023",
        "description": "Online Transfer From Chk 1212",
        "amount": 10000.00
      }
    ],
    "withdrawals": [
      {
        "date": "01/03/2023",
        "description": "Online International Wire Transfer",
        "amount": 1428.73,
        "tax_category": "International Subcontractors"
      }
    ]
  }
}
```

## Example Error Response
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_ACCOUNT",
    "message": "Account number does not match any known accounts"
  }
}
```
