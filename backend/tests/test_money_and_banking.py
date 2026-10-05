from decimal import Decimal
import asyncio
from app.services import money
from app.providers.banking import MockBankingProvider

def test_money_rounds_half_up_to_cents():
    assert money(Decimal("1.005")) == Decimal("1.01")
    assert money(Decimal("-1.005")) == Decimal("-1.01")

def test_mock_banking_has_plausible_account_and_transactions():
    provider = MockBankingProvider()
    async def check():
        account = await provider.get_account("demo")
        assert account["currency"] == "DKK"
        assert "4821" in account["masked_number"]
        transactions = await provider.get_transactions("demo")
        assert len(transactions) >= 3
        assert all(isinstance(row["amount"], Decimal) for row in transactions)
    asyncio.run(check())

def test_enable_banking_jwt_and_response_parsing(tmp_path):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    import json
    import base64
    from app.providers.banking import EnableBankingProvider

    # Generate a temporary test key
    key = rsa.generate_private_key(65537, 2048)
    key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    key_file = tmp_path / "test_key.pem"
    key_file.write_bytes(key_pem)

    provider = EnableBankingProvider(app_id="test-app-id-123", key_path=str(key_file))
    jwt = provider._make_jwt()
    parts = jwt.split(".")
    assert len(parts) == 3

    # Decode header and payload
    def b64_decode(s):
        padded = s + "=" * ((4 - len(s) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))

    header = b64_decode(parts[0])
    payload = b64_decode(parts[1])

    assert header["alg"] == "RS256"
    assert header["kid"] == "test-app-id-123"
    assert payload["iss"] == "enablebanking.com"
    assert payload["aud"] == "api.enablebanking.com"
    assert payload["exp"] > payload["iat"]

def test_banking_routes_mapping():
    from app.api.v1.router import router
    route_endpoints = {r.path: r.endpoint.__name__ for r in router.routes if "GET" in r.methods}
    assert route_endpoints.get("/banking/accounts") == "bank_accounts"
    assert route_endpoints.get("/banking/aspsps") == "get_banking_aspsps"
    assert route_endpoints.get("/banking/transactions") == "bank_transactions"


def test_mock_banking_advances_balance_and_transactions_on_sync():
    provider = MockBankingProvider()
    provider.reset_state()

    async def check():
        # Initial check
        balances = await provider.get_balances("mock-account-1")
        assert balances[0]["amount"] == Decimal("48250.00")
        txs_initial = await provider.get_transactions("mock-account-1")
        assert len(txs_initial) == 3

        # First sync step: advances with next simulated transaction (+5250.00)
        new_tx = await provider.advance_mock_sync("mock-account-1")
        assert new_tx["amount"] == Decimal("5250.00")
        balances_step1 = await provider.get_balances("mock-account-1")
        assert balances_step1[0]["amount"] == Decimal("53500.00")
        txs_step1 = await provider.get_transactions("mock-account-1")
        assert len(txs_step1) == 4
        assert txs_step1[0]["id"] == "mock-tx-4"

        # Second sync step: advances with next simulated transaction (-320.00)
        new_tx2 = await provider.advance_mock_sync("mock-account-1")
        assert new_tx2["amount"] == Decimal("-320.00")
        balances_step2 = await provider.get_balances("mock-account-1")
        assert balances_step2[0]["amount"] == Decimal("53180.00")
        txs_step2 = await provider.get_transactions("mock-account-1")
        assert len(txs_step2) == 5
        assert txs_step2[0]["id"] == "mock-tx-5"

    asyncio.run(check())


def test_enable_banking_parse_balances_dict_and_list(monkeypatch):
    from app.providers.banking import EnableBankingProvider

    provider = EnableBankingProvider(app_id="dummy", key_path=None)

    # 1. Dict with "balances" list
    monkeypatch.setattr(
        provider,
        "_sync_request",
        lambda method, path, *args, **kwargs: {
            "balances": [
                {
                    "balance_type": "CLBD",
                    "balance_amount": {"amount": "75200.50", "currency": "DKK"},
                    "name": "closingBooked",
                }
            ]
        },
    )

    async def check_dict():
        res = await provider.get_balances("acc-123")
        assert len(res) == 1
        assert res[0]["amount"] == Decimal("75200.50")
        assert res[0]["currency"] == "DKK"
        assert res[0]["name"] == "closingBooked"

    asyncio.run(check_dict())

    # 2. List format
    monkeypatch.setattr(
        provider,
        "_sync_request",
        lambda method, path, *args, **kwargs: [
            {
                "balance_type": "ITAV",
                "balance_amount": {"amount": "12345.67", "currency": "EUR"},
            }
        ],
    )

    async def check_list():
        res = await provider.get_balances("acc-123")
        assert len(res) == 1
        assert res[0]["amount"] == Decimal("12345.67")
        assert res[0]["currency"] == "EUR"
        assert res[0]["name"] == "ITAV"

    asyncio.run(check_list())


def test_bank_sync_endpoint_updates_balance_and_transactions():
    from types import SimpleNamespace
    from uuid import uuid4
    from app.api.v1.router import bank_sync
    from app.models.entities import BankAccount, BankTransaction

    org_id = uuid4()
    m = SimpleNamespace(organization_id=org_id)
    MockBankingProvider.reset_state()

    class TestDB:
        def __init__(self):
            self.entities = []

        def add(self, entity):
            if not getattr(entity, "id", None):
                entity.id = uuid4()
            self.entities.append(entity)

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def execute(self, statement):
            sql = str(statement.compile(compile_kwargs={"literal_binds": True})).lower()
            if "from bank_accounts" in sql:
                accs = [e for e in self.entities if isinstance(e, BankAccount)]
                class Result:
                    def scalars(self):
                        class Scalars:
                            def all(self):
                                return accs
                        return Scalars()
                return Result()
            return None

        async def scalar(self, statement):
            sql = str(statement.compile(compile_kwargs={"literal_binds": True})).lower()
            if "from bank_transactions" in sql:
                for e in self.entities:
                    if isinstance(e, BankTransaction):
                        if getattr(e, "provider_transaction_id", "") in sql:
                            return e
                return None
            return None

    db = TestDB()

    async def run_sync():
        # First sync: seeds demo account and advances to mock-tx-4 (+5250.00)
        res1 = await bank_sync(m=m, db=db)
        assert res1["status"] == "synced"
        assert res1["new_transactions"] >= 1
        assert res1["accounts"][0]["balance"] == "53500.00"

        # Check account in DB has updated balance
        acc = [e for e in db.entities if isinstance(e, BankAccount)][0]
        assert acc.balance == Decimal("53500.00")

        # Second sync: advances to mock-tx-5 (-320.00)
        res2 = await bank_sync(m=m, db=db)
        assert res2["status"] == "synced"
        assert res2["new_transactions"] == 1
        assert res2["accounts"][0]["balance"] == "53180.00"
        assert acc.balance == Decimal("53180.00")

    asyncio.run(run_sync())



