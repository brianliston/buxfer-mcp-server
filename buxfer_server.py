#!/usr/bin/env python3
"""
Simple Buxfer MCP Server - Manage your Buxfer transactions and accounts
"""
import os
import sys
import asyncio
import logging
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("buxfer-server")

# Initialize MCP server - NO PROMPT PARAMETER!
mcp = FastMCP("buxfer")

# Configuration
BUXFER_API_BASE = "https://www.buxfer.com/api"
BUXFER_TOKEN = os.environ.get("BUXFER_TOKEN", "")

# === UTILITY FUNCTIONS ===

def fmt_amount(value):
    """Format a monetary value, tolerating string amounts from the API."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)

def format_account(account):
    """Format a single account for display."""
    balance = account.get("balance", 0)
    last_synced = account.get("lastSynced", "Never")
    return f"• {account.get('name', 'Unknown')} ({account.get('bank', 'N/A')})\n  ID: {account.get('id', 'N/A')}\n  Balance: {fmt_amount(balance)}\n  Last Synced: {last_synced}"

def format_transaction(txn):
    """Format a single transaction for display."""
    amount = txn.get("amount", 0)
    txn_type = txn.get("type", "unknown")
    status = txn.get("status", "")
    tags = txn.get("tags", "")
    account_name = txn.get("accountName", "Unknown")
    
    result = f"• {txn.get('description', 'No description')} ({txn.get('date', 'No date')})\n"
    result += f"  ID: {txn.get('id', 'N/A')}\n"
    result += f"  Type: {txn_type} | Amount: {fmt_amount(amount)}\n"
    result += f"  Account: {account_name}"
    
    if status:
        result += f" | Status: {status}"
    if tags:
        result += f" | Tags: {tags}"
    
    extra_info = txn.get("extraInfo", "")
    if extra_info:
        result += f"\n  Info: {extra_info}"
    
    return result

async def make_buxfer_request(method, endpoint, params=None, data=None):
    """Make a request to the Buxfer API."""
    if not BUXFER_TOKEN:
        raise ValueError("BUXFER_TOKEN environment variable not set")
    
    url = f"{BUXFER_API_BASE}/{endpoint}"
    
    # Add token to query params
    if params is None:
        params = {}
    params["token"] = BUXFER_TOKEN
    
    # httpx error messages include the request URL (which carries the token),
    # so never let them propagate verbatim.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, params=params, data=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Buxfer API returned HTTP {e.response.status_code} for endpoint '{endpoint}'") from None
    except httpx.HTTPError as e:
        raise ValueError(f"HTTP error ({type(e).__name__}) calling Buxfer endpoint '{endpoint}'") from None

    # Check for API-level errors
    if "response" in result:
        status = result["response"].get("status", "")
        if status.startswith("ERROR"):
            raise ValueError(f"Buxfer API error: {status}")

    return result

# === MCP TOOLS ===

@mcp.tool()
async def add_transaction(description: str = "", amount: str = "", account_id: str = "", account_name: str = "", date: str = "", tags: str = "", transaction_type: str = "expense", status: str = "cleared") -> str:
    """Add a new transaction to Buxfer with description, amount, account, date, tags, type (expense/income/transfer/loan/etc), and status (cleared/pending)."""
    logger.info(f"Adding transaction: {description}")
    
    try:
        if not description:
            return "❌ Error: Description is required"
        if not amount:
            return "❌ Error: Amount is required"
        if not account_id and not account_name:
            return "❌ Error: Either account_id or account_name is required"
        
        # Prepare data
        data = {
            "description": description,
            "amount": amount,
            "type": transaction_type,
            "status": status
        }
        
        if account_id:
            data["accountId"] = account_id
        if account_name:
            data["accountName"] = account_name
        if date:
            data["date"] = date
        if tags:
            data["tags"] = tags
        
        result = await make_buxfer_request("POST", "transaction_add", data=data)
        
        if "response" in result:
            txn = result["response"]
            response_text = "✅ Transaction added successfully!\n\n"
            response_text += f"ID: {txn.get('id', 'N/A')}\n"
            response_text += f"Description: {txn.get('description', 'N/A')}\n"
            response_text += f"Amount: {fmt_amount(txn.get('amount', 0))}\n"
            response_text += f"Type: {txn.get('type', 'N/A')}\n"
            response_text += f"Date: {txn.get('date', 'N/A')}\n"
            response_text += f"Account: {txn.get('accountName', 'N/A')}\n"
            response_text += f"Status: {txn.get('status', 'N/A')}"
            
            if txn.get('tags'):
                response_text += f"\nTags: {txn.get('tags')}"
            
            return response_text
        
        return "❌ Error: Unexpected response format from Buxfer API"
        
    except Exception as e:
        logger.error(f"Error adding transaction: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def edit_transaction(transaction_id: str = "", description: str = "", amount: str = "", account_id: str = "", date: str = "", tags: str = "", transaction_type: str = "", status: str = "") -> str:
    """Edit an existing Buxfer transaction by transaction_id. Only the fields you pass are changed; leave others empty to keep them. Editable fields: description, amount, account_id, date (YYYY-MM-DD), tags, transaction_type (expense/income/transfer/loan/etc), status (cleared/pending)."""
    logger.info(f"Editing transaction: {transaction_id}")

    try:
        if not transaction_id:
            return "❌ Error: transaction_id is required"

        data = {"id": transaction_id}

        if description:
            data["description"] = description
        if amount:
            data["amount"] = amount
        if account_id:
            data["accountId"] = account_id
        if date:
            data["date"] = date
        if tags:
            data["tags"] = tags
        if transaction_type:
            data["type"] = transaction_type
        if status:
            data["status"] = status

        if len(data) == 1:
            return "❌ Error: Provide at least one field to edit"

        result = await make_buxfer_request("POST", "transaction_edit", data=data)

        if "response" in result:
            txn = result["response"]
            response_text = "✅ Transaction updated successfully!\n\n"
            response_text += f"ID: {txn.get('id', transaction_id)}\n"
            response_text += f"Description: {txn.get('description', 'N/A')}\n"
            response_text += f"Amount: {fmt_amount(txn.get('amount', 0))}\n"
            response_text += f"Type: {txn.get('type', 'N/A')}\n"
            response_text += f"Date: {txn.get('date', 'N/A')}\n"
            response_text += f"Account: {txn.get('accountName', 'N/A')}\n"
            response_text += f"Status: {txn.get('status', 'N/A')}"

            if txn.get('tags'):
                response_text += f"\nTags: {txn.get('tags')}"

            return response_text

        return "❌ Error: Unexpected response format from Buxfer API"

    except Exception as e:
        logger.error(f"Error editing transaction: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def list_accounts() -> str:
    """Get all Buxfer accounts with their current balances, IDs, banks, and last sync times."""
    logger.info("Fetching accounts list")
    
    try:
        result = await make_buxfer_request("GET", "accounts")
        
        if "response" in result and "accounts" in result["response"]:
            accounts = result["response"]["accounts"]
            
            if not accounts:
                return "ℹ️ No accounts found"
            
            response_text = f"📊 **Buxfer Accounts** ({len(accounts)} total)\n\n"
            
            for account in accounts:
                response_text += format_account(account) + "\n\n"
            
            # Calculate total balance
            total_balance = 0.0
            for acc in accounts:
                try:
                    total_balance += float(acc.get("balance", 0))
                except (TypeError, ValueError):
                    pass
            response_text += f"**Total Balance: {fmt_amount(total_balance)}**"
            
            return response_text
        
        return "❌ Error: Unexpected response format from Buxfer API"
        
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return f"❌ Error: {str(e)}"

MAX_AUTO_PAGES = 60  # safety cap when auto-paginating client-side filters (~6000 txns)
MAX_DISPLAY = 200    # cap on how many transactions to render in one response

async def fetch_all_transactions(params):
    """Fetch all pages for the given server-side filters. Returns (transactions, num_total, truncated)."""
    first = await make_buxfer_request("GET", "transactions", params={**params, "page": 1})
    resp = first.get("response", {})
    transactions = list(resp.get("transactions", []))
    num_total = int(resp.get("numTransactions", 0))
    total_pages = (num_total + 99) // 100
    pages_to_fetch = min(total_pages, MAX_AUTO_PAGES)

    # Fetch remaining pages concurrently (bounded), preserving page order
    semaphore = asyncio.Semaphore(5)

    async def fetch_page(p):
        async with semaphore:
            r = await make_buxfer_request("GET", "transactions", params={**params, "page": p})
            return r.get("response", {}).get("transactions", [])

    pages = await asyncio.gather(*(fetch_page(p) for p in range(2, pages_to_fetch + 1)))
    for page_txns in pages:
        transactions.extend(page_txns)

    return transactions, num_total, total_pages > MAX_AUTO_PAGES

@mcp.tool()
async def list_transactions(account_id: str = "", account_name: str = "", tag_name: str = "", start_date: str = "", end_date: str = "", month: str = "", status: str = "", transaction_type: str = "", untagged: bool = False, page: str = "1") -> str:
    """Get transactions from Buxfer with optional filters: account_id, account_name, tag_name, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), month (e.g. 'jan 2024'), status (pending/cleared/reconciled), transaction_type (e.g. expense/income/transfer), untagged (true to show only transactions with no tags), page number for pagination. When transaction_type or untagged is set, all pages in the date range are fetched and filtered (scope with a date range for best results)."""
    logger.info("Fetching transactions")

    try:
        params = {}

        if account_id:
            params["accountId"] = account_id
        if account_name:
            params["accountName"] = account_name
        if tag_name:
            params["tagName"] = tag_name
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if month:
            params["month"] = month
        if status:
            params["status"] = status

        want_untagged = untagged
        client_filtering = bool(transaction_type) or want_untagged

        # Build the shared filter-description line
        filters_applied = []
        if account_name:
            filters_applied.append(f"Account: {account_name}")
        elif account_id:
            filters_applied.append(f"Account ID: {account_id}")
        if tag_name:
            filters_applied.append(f"Tag: {tag_name}")
        if start_date and end_date:
            filters_applied.append(f"Date: {start_date} to {end_date}")
        elif month:
            filters_applied.append(f"Month: {month}")
        if status:
            filters_applied.append(f"Status: {status}")
        if transaction_type:
            filters_applied.append(f"Type: {transaction_type}")
        if want_untagged:
            filters_applied.append("Untagged only")

        if client_filtering:
            transactions, num_total, truncated = await fetch_all_transactions(params)

            if transaction_type:
                transactions = [t for t in transactions if t.get("type", "").lower() == transaction_type.lower()]
            if want_untagged:
                transactions = [t for t in transactions if not t.get("tags")]

            if not transactions:
                return "ℹ️ No transactions found matching your criteria"

            total_amount = 0.0
            for t in transactions:
                try:
                    total_amount += float(t.get("amount", 0))
                except (TypeError, ValueError):
                    pass
            response_text = f"📋 **Buxfer Transactions** ({len(transactions)} matching, scanned {num_total} total)\n\n"
            if filters_applied:
                response_text += f"**Filters:** {', '.join(filters_applied)}\n\n"
            if truncated:
                response_text += f"⚠️ Only the most recent {MAX_AUTO_PAGES * 100} transactions were scanned — narrow the date range for a complete view.\n\n"

            for txn in transactions[:MAX_DISPLAY]:
                response_text += format_transaction(txn) + "\n\n"
            if len(transactions) > MAX_DISPLAY:
                response_text += f"…and {len(transactions) - MAX_DISPLAY} more (showing first {MAX_DISPLAY}).\n\n"

            response_text += f"**Total matching amount: ${total_amount:,.2f}**"
            return response_text

        # Default: single-page behavior
        if page:
            params["page"] = page

        result = await make_buxfer_request("GET", "transactions", params=params)

        if "response" in result and "transactions" in result["response"]:
            transactions = result["response"]["transactions"]
            num_total = int(result["response"].get("numTransactions", 0))

            if not transactions:
                return "ℹ️ No transactions found matching your criteria"

            current_page = int(page) if page else 1
            response_text = f"📋 **Buxfer Transactions** (Page {current_page}, {len(transactions)} of {num_total} total)\n\n"

            if filters_applied:
                response_text += f"**Filters:** {', '.join(filters_applied)}\n\n"

            for txn in transactions:
                response_text += format_transaction(txn) + "\n\n"

            # Add pagination info
            if num_total > len(transactions):
                total_pages = (num_total + 99) // 100  # Round up
                response_text += f"**Page {current_page} of {total_pages}** (Use page parameter to view more)"

            return response_text

        return "❌ Error: Unexpected response format from Buxfer API"

    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def list_budgets() -> str:
    """Get all Buxfer budgets with their limits, remaining amounts, periods, and associated tags."""
    logger.info("Fetching budgets list")

    try:
        result = await make_buxfer_request("GET", "budgets")

        if "response" in result and "budgets" in result["response"]:
            budgets = result["response"]["budgets"]

            if not budgets:
                return "ℹ️ No budgets found"

            response_text = f"📊 **Buxfer Budgets** ({len(budgets)} total)\n\n"

            for budget in budgets:
                limit = budget.get("limit", "N/A")
                remaining = budget.get("remaining", 0)
                response_text += f"• {budget.get('name', 'Unknown')}\n"
                response_text += f"  ID: {budget.get('id', 'N/A')}\n"
                response_text += f"  Limit: {limit} | Remaining: {fmt_amount(remaining)}\n"
                response_text += f"  Period: {budget.get('period', 'N/A')}"
                if budget.get("currentPeriod"):
                    response_text += f" ({budget.get('currentPeriod')})"
                if budget.get("tags"):
                    response_text += f"\n  Tags: {budget.get('tags')}"
                response_text += "\n\n"

            return response_text

        return "❌ Error: Unexpected response format from Buxfer API"

    except Exception as e:
        logger.error(f"Error listing budgets: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def list_tags() -> str:
    """Get all Buxfer transaction tags with their IDs and parent tag relationships."""
    logger.info("Fetching tags list")

    try:
        result = await make_buxfer_request("GET", "tags")

        if "response" in result and "tags" in result["response"]:
            tags = result["response"]["tags"]

            if not tags:
                return "ℹ️ No tags found"

            response_text = f"🏷️ **Buxfer Tags** ({len(tags)} total)\n\n"

            for tag in tags:
                response_text += f"• {tag.get('name', 'Unknown')}\n"
                response_text += f"  ID: {tag.get('id', 'N/A')}"
                parent_id = tag.get("parentId", -1)
                if parent_id and parent_id != -1:
                    response_text += f" | Parent ID: {parent_id}"
                response_text += "\n\n"

            return response_text

        return "❌ Error: Unexpected response format from Buxfer API"

    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        return f"❌ Error: {str(e)}"

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Buxfer MCP server...")
    
    if not BUXFER_TOKEN:
        logger.warning("BUXFER_TOKEN not set - server will not be able to make API calls")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
