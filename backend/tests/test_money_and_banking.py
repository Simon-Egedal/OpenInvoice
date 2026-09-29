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
