import asyncio
import base64
import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def _b64url(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")


class BankingProvider(ABC):
    @abstractmethod
    async def get_aspsps(self, country: str = "DK") -> list[dict]: ...

    @abstractmethod
    async def create_authorization(
        self,
        callback_url: str,
        aspsp_name: str | None = None,
        aspsp_country: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def handle_callback(self, code: str) -> dict: ...

    @abstractmethod
    async def get_accounts(self, connection_id: str) -> list[dict]: ...

    @abstractmethod
    async def get_account(self, account_id: str) -> dict: ...

    @abstractmethod
    async def get_balances(self, account_id: str) -> list[dict]: ...

    @abstractmethod
    async def get_transactions(self, account_id: str) -> list[dict]: ...

    @abstractmethod
    async def disconnect(self, connection_id: str) -> None: ...


class MockBankingProvider(BankingProvider):
    _initial_balance = Decimal("48250.00")
    _sync_pool = [
        ("Customer payment - Inv 2026-0055", "Nordic Solutions ApS", Decimal("5250.00"), "2026-0055"),
        ("Software subscription", "GitHub Inc.", Decimal("-320.00"), None),
        ("Consulting retainer", "København Media Group", Decimal("12800.00"), "2026-0060"),
        ("Office supplies & coffee", "Kaffebaren ApS", Decimal("-450.00"), None),
        ("Invoice 2026-0072 settlement", "Aarhus Design Lab", Decimal("7400.00"), "2026-0072"),
        ("Telecom & internet", "TDC Net", Decimal("-899.00"), None),
        ("Marketing campaign", "Google Ads", Decimal("-1500.00"), None),
        ("Client payment - Inv 2026-0081", "Odense Logistics", Decimal("9200.00"), "2026-0081"),
    ]
    _account_states: dict[str, dict] = {}

    @classmethod
    def reset_state(cls):
        cls._account_states = {}

    def _get_account_state(self, account_id: str, current_balance: Decimal | None = None) -> dict:
        key = str(account_id or "mock-account-1")
        if key not in self._account_states:
            init_bal = current_balance if current_balance is not None else self._initial_balance
            self._account_states[key] = {
                "balance": init_bal,
                "synced_count": 0,
                "extra_transactions": [],
            }
        elif current_balance is not None:
            self._account_states[key]["balance"] = current_balance
        return self._account_states[key]

    async def advance_mock_sync(self, account_id: str, current_balance: Decimal | None = None) -> dict:
        state = self._get_account_state(account_id, current_balance)
        count = state["synced_count"]
        now = datetime.now(timezone.utc)
        if count < len(self._sync_pool):
            d, p, a, ref = self._sync_pool[count]
        else:
            idx = count + 1
            if idx % 2 == 1:
                d, p, a, ref = (f"Client payment - Inv 2026-{100 + idx}", "Danmark Business Partner ApS", Decimal("3500.00"), f"2026-{100 + idx}")
            else:
                d, p, a, ref = (f"Operational expense #{idx}", "Kontor & Service ApS", Decimal("-650.00"), None)

        new_tx = {
            "id": f"mock-tx-{4 + count}",
            "booked_at": now,
            "description": d,
            "counterparty": p,
            "amount": a,
            "currency": "DKK",
            "reference": ref,
        }
        state["extra_transactions"].append(new_tx)
        state["balance"] += a
        state["synced_count"] += 1
        return new_tx

    async def get_aspsps(self, country: str = "DK") -> list[dict]:
        return [
            {"name": "Nordic Bank (demo)", "country": country.upper(), "logo": None, "psu_types": ["personal", "business"]}
        ]

    async def create_authorization(
        self,
        callback_url: str,
        aspsp_name: str | None = None,
        aspsp_country: str | None = None,
    ) -> str:
        return f"{callback_url}?code=mock-{uuid4()}"

    async def handle_callback(self, code: str) -> dict:
        return {
            "session_id": code,
            "provider": "mock",
            "aspsp": {"name": "Nordic Bank (demo)", "country": "DK"},
            "accounts": [
                {
                    "id": "mock-account-1",
                    "uid": "mock-account-1",
                    "name": "Business account",
                    "bank": "Nordic Bank (demo)",
                    "masked_number": "•••• 4821",
                    "currency": "DKK",
                    "account_id": {"iban": "DK12345678904821"},
                }
            ],
        }

    async def get_accounts(self, connection_id: str) -> list[dict]:
        return [await self.get_account("mock-account-1")]

    async def get_account(self, account_id: str) -> dict:
        return {
            "id": account_id,
            "uid": account_id,
            "name": "Business account",
            "bank": "Nordic Bank (demo)",
            "masked_number": "•••• 4821",
            "currency": "DKK",
            "account_id": {"iban": "DK12345678904821"},
        }

    async def get_balances(self, account_id: str) -> list[dict]:
        state = self._get_account_state(account_id)
        return [{"amount": state["balance"], "currency": "DKK", "name": "Booked balance"}]

    async def get_transactions(self, account_id: str) -> list[dict]:
        now = datetime.now(timezone.utc)
        base = [
            {
                "id": f"mock-tx-{i}",
                "booked_at": now - timedelta(days=i * 3),
                "description": d,
                "counterparty": p,
                "amount": Decimal(a),
                "currency": "DKK",
                "reference": ref,
            }
            for i, (d, p, a, ref) in enumerate(
                [
                    ("Invoice 2026-0042", "Acme ApS", "4995.00", "2026-0042"),
                    ("Office supplies", "Paper Shop", "-842.50", None),
                    ("Cloud hosting", "Example Cloud", "-1299.00", None),
                ],
                1,
            )
        ]
        state = self._get_account_state(account_id)
        extras = list(reversed(state["extra_transactions"]))
        return extras + base

    async def disconnect(self, connection_id: str) -> None:
        return None


class EnableBankingProvider(BankingProvider):
    """Enable Banking open banking aggregation provider."""

    def __init__(
        self,
        app_id: str | None = None,
        key_path: str | None = None,
        api_origin: str = "https://api.enablebanking.com",
    ):
        self.app_id = app_id
        self.key_path = key_path
        self.api_origin = api_origin.rstrip("/")

    def _resolve_credentials(self) -> tuple[str, bytes]:
        from app.core.config import settings

        app_id = self.app_id or settings.enable_banking_app_id
        key_path = self.key_path or settings.enable_banking_private_key_path
        if not app_id:
            raise ValueError(
                "Enable Banking application ID is not configured. Please set it in Settings -> Infrastructure."
            )
        key_bytes = self._load_key_bytes(key_path)
        return app_id, key_bytes

    def _load_key_bytes(self, configured_path: str | None) -> bytes:
        candidates = []
        if configured_path:
            candidates.append(Path(configured_path))
        candidates.extend([
            Path("/run/secrets/enable-banking.pem"),
            Path("/run/secrets/eneble-banking.pem"),
            Path("./secrets/enable-banking.pem"),
            Path("./secrets/eneble-banking.pem"),
            Path("../secrets/enable-banking.pem"),
            Path("/data/secrets/enable-banking.pem"),
        ])
        for p in candidates:
            try:
                if p.exists() and p.is_file():
                    return p.read_bytes()
            except Exception:
                continue
        raise FileNotFoundError(
            f"Enable Banking private key file was not found (configured path: '{configured_path}'). "
            "Please ensure the .pem key file exists in secrets/ or /run/secrets/."
        )

    def _make_jwt(self) -> str:
        app_id, key_bytes = self._resolve_credentials()
        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT", "kid": app_id}
        payload = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": now,
            "exp": now + 3600,
        }
        h_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        private_key = load_pem_private_key(key_bytes, password=None)
        sig = _b64url(private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))
        return f"{h_b64}.{p_b64}.{sig}"

    def _sync_request(self, method: str, path: str, payload: dict | None = None, query: dict | None = None) -> Any:
        jwt = self._make_jwt()
        url = f"{self.api_origin}{path}"
        if query:
            url += ("?" + urlencode({k: v for k, v in query.items() if v is not None}))
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {jwt}",
                "Content-Type": "application/json",
                "User-Agent": "OpenInvoice/1.0",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            try:
                err_body = exc.read().decode("utf-8")
                err_data = json.loads(err_body)
                msg = err_data.get("message") or err_data.get("error") or err_body
            except Exception:
                msg = f"HTTP {exc.code} {exc.reason}"
            raise RuntimeError(f"Enable Banking API error ({exc.code}): {msg}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to communicate with Enable Banking API: {exc}") from exc

    async def get_aspsps(self, country: str = "DK") -> list[dict]:
        data = await asyncio.to_thread(self._sync_request, "GET", "/aspsps", None, {"country": country.upper()})
        items = data.get("aspsps") if isinstance(data, dict) and "aspsps" in data else data
        return items if isinstance(items, list) else []

    async def create_authorization(
        self,
        callback_url: str,
        aspsp_name: str | None = None,
        aspsp_country: str | None = None,
    ) -> str:
        country = (aspsp_country or "DK").upper()
        if not aspsp_name:
            banks = await self.get_aspsps(country)
            chosen = None
            for b in banks:
                if "mock" in b.get("name", "").lower():
                    chosen = b
                    break
            if not chosen and banks:
                chosen = banks[0]
            if chosen:
                aspsp_name = chosen["name"]
            else:
                aspsp_name = "Mock ASPSP"

        body = {
            "access": {
                "valid_until": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
            },
            "aspsp": {"name": aspsp_name, "country": country},
            "state": str(uuid4()),
            "redirect_url": callback_url,
            "psu_type": "personal",
        }
        res = await asyncio.to_thread(self._sync_request, "POST", "/auth", body)
        if not res or "url" not in res:
            raise RuntimeError("Enable Banking did not return an authorization URL")
        return res["url"]

    async def handle_callback(self, code: str) -> dict:
        body = {"code": code}
        session_data = await asyncio.to_thread(self._sync_request, "POST", "/sessions", body)
        return {
            "session_id": session_data.get("session_id"),
            "accounts": session_data.get("accounts", []),
            "aspsp": session_data.get("aspsp", {}),
            "provider": "enable_banking",
        }

    async def get_accounts(self, connection_id: str) -> list[dict]:
        data = await asyncio.to_thread(self._sync_request, "GET", f"/sessions/{connection_id}")
        return data.get("accounts", [])

    async def get_account(self, account_id: str) -> dict:
        data = await asyncio.to_thread(self._sync_request, "GET", f"/accounts/{account_id}/details")
        return data

    async def get_balances(self, account_id: str) -> list[dict]:
        data = await asyncio.to_thread(self._sync_request, "GET", f"/accounts/{account_id}/balances")
        raw_balances = []
        if isinstance(data, dict):
            raw_balances = data.get("balances", [])
            if not raw_balances and ("balance_amount" in data or "amount" in data):
                raw_balances = [data]
        elif isinstance(data, list):
            raw_balances = data

        results = []
        for b in raw_balances:
            if not isinstance(b, dict):
                continue
            amt_info = b.get("balance_amount") or b.get("balanceAmount") or b
            if isinstance(amt_info, dict):
                amt_str = str(
                    amt_info.get("amount")
                    if amt_info.get("amount") is not None
                    else amt_info.get("value", "0")
                )
                curr = amt_info.get("currency") or b.get("currency", "DKK")
            else:
                amt_str = str(amt_info)
                curr = b.get("currency", "DKK")
            try:
                amt = Decimal(amt_str)
            except Exception:
                amt = Decimal("0.00")
            name = b.get("name") or b.get("balance_type") or b.get("balanceType") or "Current balance"
            results.append({"amount": amt, "currency": str(curr).upper()[:3], "name": str(name)})
        return results

    async def get_transactions(self, account_id: str) -> list[dict]:
        query = {
            "date_from": (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat(),
        }
        data = await asyncio.to_thread(self._sync_request, "GET", f"/accounts/{account_id}/transactions", None, query)
        raw_txs = data.get("transactions", []) if isinstance(data, dict) else []
        results = []
        for t in raw_txs:
            amt_info = t.get("transaction_amount") or {}
            amt = Decimal(str(amt_info.get("amount", "0")))
            indicator = t.get("credit_debit_indicator", "CRDT")
            if indicator == "DBIT" and amt > 0:
                amt = -amt
            curr = amt_info.get("currency", "DKK")
            remit = t.get("remittance_information", [])
            desc = (
                remit[0]
                if (remit and isinstance(remit, list))
                else (t.get("debtor_name") or t.get("creditor_name") or "Bank Transaction")
            )
            counterparty = t.get("creditor_name") if indicator == "DBIT" else t.get("debtor_name")
            booking_date = t.get("booking_date") or t.get("value_date")
            booked_at = (
                datetime.fromisoformat(booking_date).replace(tzinfo=timezone.utc)
                if booking_date
                else datetime.now(timezone.utc)
            )
            results.append({
                "id": str(t.get("entry_reference") or uuid4()),
                "booked_at": booked_at,
                "description": str(desc)[:300],
                "counterparty": str(counterparty or "")[:200],
                "amount": amt,
                "direction": "debit" if indicator == "DBIT" else "credit",
                "currency": str(curr).upper()[:3],
                "reference": str(t.get("entry_reference") or "")[:200] or None,
            })
        return results

    async def disconnect(self, connection_id: str) -> None:
        try:
            await asyncio.to_thread(self._sync_request, "DELETE", f"/sessions/{connection_id}")
        except Exception:
            pass


def get_banking_provider() -> BankingProvider:
    from app.core.config import settings

    if settings.banking_provider == "enable_banking":
        return EnableBankingProvider()
    return MockBankingProvider()
