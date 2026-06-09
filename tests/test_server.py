"""Tests for buxfer_server. Run with: python -m pytest tests/ -v"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("BUXFER_TOKEN", "test-token")

import buxfer_server


def run(coro):
    return asyncio.run(coro)


# === fmt_amount ===

def test_fmt_amount_float():
    assert buxfer_server.fmt_amount(1234.5) == "$1,234.50"


def test_fmt_amount_string():
    assert buxfer_server.fmt_amount("1234.5") == "$1,234.50"


def test_fmt_amount_garbage():
    assert buxfer_server.fmt_amount("N/A") == "N/A"
    assert buxfer_server.fmt_amount(None) == "None"


# === token never leaks via HTTP errors ===

def _mock_client_raising(exc):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = exc
    client.post.side_effect = exc
    return client


def test_http_status_error_scrubs_token():
    token = "secret-token-value"
    url = f"https://www.buxfer.com/api/accounts?token={token}"
    request = httpx.Request("GET", url)
    response = httpx.Response(401, request=request)
    exc = httpx.HTTPStatusError("Client error '401' for url " + url, request=request, response=response)

    with patch.object(buxfer_server, "BUXFER_TOKEN", token), \
         patch("httpx.AsyncClient", return_value=_mock_client_raising(exc)):
        with pytest.raises(ValueError) as ei:
            run(buxfer_server.make_buxfer_request("GET", "accounts"))
    assert token not in str(ei.value)
    assert "401" in str(ei.value)


def test_connect_error_scrubs_token():
    token = "secret-token-value"
    exc = httpx.ConnectError(f"failed to connect https://www.buxfer.com/api/accounts?token={token}")

    with patch.object(buxfer_server, "BUXFER_TOKEN", token), \
         patch("httpx.AsyncClient", return_value=_mock_client_raising(exc)):
        with pytest.raises(ValueError) as ei:
            run(buxfer_server.make_buxfer_request("GET", "accounts"))
    assert token not in str(ei.value)


def test_missing_token_raises():
    with patch.object(buxfer_server, "BUXFER_TOKEN", ""):
        with pytest.raises(ValueError):
            run(buxfer_server.make_buxfer_request("GET", "accounts"))


# === add_transaction ===

def test_add_transaction_requires_fields():
    assert "Description is required" in run(buxfer_server.add_transaction())
    assert "Amount is required" in run(buxfer_server.add_transaction(description="x"))
    assert "account_id or account_name" in run(
        buxfer_server.add_transaction(description="x", amount="5")
    )


def test_add_transaction_string_amount_response():
    """API echoing amount back as a string must not turn success into an error."""
    mock_result = {"response": {"id": 1, "description": "Coffee", "amount": "4.50",
                                "type": "expense", "date": "2026-06-10",
                                "accountName": "Cash", "status": "cleared"}}
    with patch.object(buxfer_server, "make_buxfer_request", AsyncMock(return_value=mock_result)):
        out = run(buxfer_server.add_transaction(description="Coffee", amount="4.50", account_name="Cash"))
    assert "✅" in out
    assert "$4.50" in out


def test_add_transaction_api_error():
    with patch.object(buxfer_server, "make_buxfer_request",
                      AsyncMock(side_effect=ValueError("Buxfer API error: ERROR"))):
        out = run(buxfer_server.add_transaction(description="x", amount="5", account_name="Cash"))
    assert "❌" in out


# === edit_transaction ===

def test_edit_transaction_requires_id_and_field():
    assert "transaction_id is required" in run(buxfer_server.edit_transaction())
    assert "at least one field" in run(buxfer_server.edit_transaction(transaction_id="123"))


# === list_accounts ===

def test_list_accounts_string_balance():
    mock_result = {"response": {"accounts": [
        {"id": 1, "name": "Checking", "bank": "Bank", "balance": "100.25"},
        {"id": 2, "name": "Savings", "bank": "Bank", "balance": 50},
    ]}}
    with patch.object(buxfer_server, "make_buxfer_request", AsyncMock(return_value=mock_result)):
        out = run(buxfer_server.list_accounts())
    assert "$100.25" in out
    assert "Total Balance: $150.25" in out


# === list_transactions ===

def test_list_transactions_single_page():
    mock_result = {"response": {"numTransactions": 1, "transactions": [
        {"id": 1, "description": "Coffee", "amount": 4.5, "type": "expense",
         "date": "2026-06-10", "accountName": "Cash"},
    ]}}
    with patch.object(buxfer_server, "make_buxfer_request", AsyncMock(return_value=mock_result)):
        out = run(buxfer_server.list_transactions())
    assert "Coffee" in out
    assert "$4.50" in out


def test_list_transactions_untagged_filter():
    mock_result = {"response": {"numTransactions": 2, "transactions": [
        {"id": 1, "description": "Tagged", "amount": 1, "type": "expense", "tags": "food"},
        {"id": 2, "description": "Untagged", "amount": 2, "type": "expense", "tags": ""},
    ]}}
    with patch.object(buxfer_server, "make_buxfer_request", AsyncMock(return_value=mock_result)):
        out = run(buxfer_server.list_transactions(untagged=True))
    assert "Untagged" in out
    assert "Tagged\n" not in out  # only the untagged txn rendered


def test_list_transactions_type_filter_paginates():
    """Client-side type filtering fetches all pages."""
    call_count = {"n": 0}

    async def fake_request(method, endpoint, params=None, data=None):
        call_count["n"] += 1
        page = params.get("page", 1)
        return {"response": {"numTransactions": 150, "transactions": [
            {"id": page, "description": f"Page{page}", "amount": 1, "type": "expense"},
        ]}}

    with patch.object(buxfer_server, "make_buxfer_request", fake_request):
        out = run(buxfer_server.list_transactions(transaction_type="expense"))
    assert call_count["n"] == 2  # 150 txns -> 2 pages
    assert "Page1" in out and "Page2" in out
