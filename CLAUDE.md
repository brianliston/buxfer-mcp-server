# BUXFER MCP SERVER - CLAUDE INTEGRATION GUIDE

## Overview
This MCP server provides Claude with the ability to manage Buxfer financial transactions and accounts through six tools: add_transaction, edit_transaction, list_accounts, list_transactions, list_budgets, and list_tags. The server uses token-based authentication and communicates with the Buxfer API via HTTPS.

## Architecture

### Technology Stack
- **Language**: Python 3.11
- **Framework**: FastMCP (MCP SDK)
- **HTTP Client**: httpx (async)
- **Execution**: Run directly via Python (no Docker required)
- **Transport**: stdio (standard input/output)

### Security Features
- **Token Authentication**: Uses pre-obtained Buxfer API token
- **Environment Variables**: Credentials stored securely in Claude config
- **HTTPS Only**: All API communications encrypted
- **No Password Storage**: Only ephemeral tokens used

## Implementation Details

### Authentication Flow
1. User obtains token via POST to `/api/login` with credentials
2. Token stored in Claude Desktop config as environment variable
3. Server reads token from `BUXFER_TOKEN` environment variable
4. Token appended as query parameter to all API requests
5. Buxfer validates token server-side for each request

### API Communication Pattern
```python
# Token passed as query parameter (not header)
GET https://www.buxfer.com/api/accounts?token=YOUR_TOKEN
POST https://www.buxfer.com/api/transaction_add?token=YOUR_TOKEN
```

### Tool Implementations

#### 1. add_transaction
**Purpose**: Create new financial transactions in Buxfer

**Key Features**:
- Supports all transaction types (expense, income, transfer, loan, etc.)
- Flexible account specification (by ID or name)
- Optional date, tags, and status parameters
- Returns formatted confirmation with transaction details

**Validation**:
- Requires: description, amount, account identifier
- Amount can be string (API handles conversion)
- Date format: YYYY-MM-DD
- Status: cleared or pending

**API Endpoint**: `POST /api/transaction_add`

#### 2. list_accounts
**Purpose**: Retrieve all user accounts with current balances

**Key Features**:
- No parameters needed
- Returns all accounts with IDs, names, banks, balances
- Calculates and displays total balance across accounts
- Shows last sync timestamp for connected accounts

**Response Format**:
- Emoji indicators for visual clarity
- Formatted currency values
- Account grouping by type
- Summary statistics

**API Endpoint**: `GET /api/accounts`

#### 3. list_transactions
**Purpose**: Query transactions with extensive filtering options

**Key Features**:
- Multiple filter types (account, tag, date, status)
- Pagination support (100 transactions per page)
- Flexible date ranges (start/end or month)
- Status filtering (pending/cleared/reconciled)

**Filter Combinations**:
- Account + Date Range
- Tag + Month
- Status + Account
- Any combination supported by API

**API Endpoint**: `GET /api/transactions`

### Error Handling

The server implements comprehensive error handling:

1. **Token Validation**: Checks for token presence before API calls
2. **HTTP Errors**: Catches and reports connection/timeout issues
3. **API Errors**: Parses Buxfer API error responses
4. **Parameter Validation**: Validates required parameters
5. **Graceful Degradation**: Returns user-friendly error messages

### Response Formatting

All tools return formatted strings with:
- **Emoji Indicators**: ✅ Success, ❌ Error, ℹ️ Info, 📊 Data, 📋 Lists
- **Structured Data**: Hierarchical display with clear sections
- **Currency Formatting**: Proper decimal places and thousand separators
- **Status Badges**: Clear indication of transaction/account states

## Claude Desktop Configuration

### Configuration File Location
- **MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Configuration Structure
```json
{
  "mcpServers": {
    "buxfer": {
      "command": "/absolute/path/to/buxfer-mcp-server/.venv/bin/python",
      "args": [
        "/absolute/path/to/buxfer-mcp-server/buxfer_server.py"
      ],
      "env": {
        "BUXFER_TOKEN": "your_actual_token_here"
      }
    }
  }
}
```

### Configuration Notes
- The server runs directly via Python; Docker is not used.
- `command` should point at the Python interpreter that has the dependencies installed (a `.venv` is recommended).
- Token passed via the `env` object as `BUXFER_TOKEN`.
- Server name "buxfer" can be customized.

## Usage Patterns

### Natural Language Examples

**Account Management**:
- "Show me all my Buxfer accounts"
- "What's my total balance across all accounts?"
- "List my checking account details"

**Transaction Creation**:
- "Add a $50 grocery expense to my Cash account"
- "Record a $2000 paycheck as income to my checking account"
- "Log a $30 restaurant expense with tag 'dining out'"

**Transaction Queries**:
- "Show my recent transactions"
- "List all expenses from last month"
- "Find all pending transactions in my credit card account"
- "Show page 2 of my transactions"

### Parameter Combinations

**Date Filtering Options**:
1. Specific range: `start_date="2024-01-01", end_date="2024-01-31"`
2. Month shorthand: `month="jan 2024"`
3. Partial month: `month="jan"`

**Account Filtering Options**:
1. By name: `account_name="Checking"`
2. By ID: `account_id="abc123def456"`

**Transaction Types**:
- expense, income, transfer, refund, payment
- loan, investment_buy, investment_sell
- sharedBill, paidForFriend, settlement

## Best Practices for Claude

### When to Use Each Tool

**Use add_transaction when**:
- User wants to record a new expense or income
- User mentions spending, earning, or financial activity
- User describes a transaction that needs logging

**Use list_accounts when**:
- User asks about their financial accounts
- User wants to see balances
- User needs account IDs for transaction creation

**Use list_transactions when**:
- User wants to review past transactions
- User asks about spending history
- User needs to find specific transactions
- User wants spending analysis by category/time

### Conversation Flow Recommendations

1. **Account Discovery First**: 
   - When adding transactions, first list accounts if user doesn't specify
   - Confirm account names before creating transactions

2. **Progressive Filtering**:
   - Start with broad queries, then narrow down
   - Use pagination for large result sets

3. **Date Handling**:
   - Default to recent data if no date specified
   - Suggest date ranges for better results

4. **Error Recovery**:
   - If transaction fails, suggest checking account names
   - Offer to list accounts if identifier invalid

## Limitations and Constraints

### API Limitations
- Maximum 100 transactions per page
- Token may expire (require refresh)
- Rate limiting may apply (not documented)

### Server Limitations
- Read-only for most endpoints (except add_transaction and edit_transaction)
- No transaction deletion in current version
- No reminder management
- No loan/group/contact management

### Runtime Limitations
- Requires Python 3.11+ with dependencies installed
- Network access required for API calls

## Troubleshooting Guide

### Common Issues

**"BUXFER_TOKEN not set"**
- Check environment variable in config
- Verify no extra spaces in token
- Confirm token hasn't expired

**"Connection refused"**
- Check internet connectivity
- Test Buxfer API availability

**"Unexpected response format"**
- May indicate API changes
- Check Buxfer API status
- Verify token is still valid

**"Module not found" / import errors**
- Ensure dependencies are installed (`pip install -r requirements.txt`)
- Confirm `command` points at the interpreter where they were installed

### Debugging Steps

1. **Check Dependencies**:
   ```bash
   .venv/bin/python -c "import mcp, httpx; print('ok')"
   ```

2. **Test API Manually**:
   ```bash
   curl "https://www.buxfer.com/api/accounts?token=YOUR_TOKEN"
   ```

3. **View Server Logs**:
   - Check Claude Desktop developer console
   - Look for stderr output from container

4. **Validate Token**:
   ```bash
   curl -X POST https://www.buxfer.com/api/login \
     -d "email=YOUR_EMAIL" \
     -d "password=YOUR_PASSWORD"
   ```

## Extension Possibilities

### Potential Future Features
1. **Transaction Editing**: Add edit and delete capabilities
2. **Budget Management**: Tools for budget CRUD operations
3. **Tag Management**: Create and manage transaction tags
4. **Loan Tracking**: Manage IOUs and group expenses
5. **Report Generation**: Generate spending reports
6. **Recurring Transactions**: Set up automatic transaction rules
7. **Statement Upload**: Upload bank statements via API

### Adding New Tools

To add a new tool:

1. **Define the tool function**:
```python
@mcp.tool()
async def new_tool(param: str = "") -> str:
    """Single-line description of the tool."""
    # Implementation
    return "Formatted result"
```

2. **Add API call**:
```python
result = await make_buxfer_request("GET", "endpoint", params={})
```

3. **Format response**:
```python
return format_new_data(result)
```

4. **Restart Claude Desktop** to pick up the new tool.

## Security Considerations

### Token Management
- **Storage**: Only in local Claude config file
- **Transmission**: Only via HTTPS to Buxfer API
- **Exposure**: Never logged or displayed
- **Rotation**: Regenerate periodically for security

### Data Privacy
- All data stays between user, Claude, and Buxfer
- No third-party data sharing
- No data persistence (no local storage of financial data)
- Logs contain no sensitive information

### Best Practices
1. Use strong Buxfer password
2. Regenerate token if compromised
3. Don't share Claude config file
4. Keep Python dependencies updated
5. Monitor API usage for anomalies

## Performance Considerations

### Optimization Strategies
- **Pagination**: Use page parameter for large datasets
- **Filtering**: Apply filters to reduce data transfer
- **Caching**: Consider caching account list (rarely changes)
- **Async**: All API calls are async for better performance

### Expected Response Times
- List accounts: < 1 second
- Add transaction: < 2 seconds
- List transactions (100): < 2 seconds
- List transactions (paginated): < 2 seconds per page

## Maintenance

### Regular Tasks
1. **Token Refresh**: When expired or compromised
2. **Dependency Updates**: Update Python packages
3. **API Monitoring**: Watch for Buxfer API changes

### Update Procedure
```bash
# Pull latest code
cd buxfer-mcp-server

# Update dependencies if needed
source .venv/bin/activate
pip install -r requirements.txt

# Restart Claude Desktop
# No config changes needed if token unchanged
```

## Support Resources

### Documentation
- Buxfer API: https://www.buxfer.com/help/api/
- FastMCP: https://github.com/modelcontextprotocol/python-sdk
- Python: https://docs.python.org/3/

### Community
- MCP Discord: For MCP-related questions
- Buxfer Support: For API-specific issues

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Compatibility**: Claude Desktop with MCP support  
**Python Version**: 3.11+  
**MCP Version**: 1.2.0+
