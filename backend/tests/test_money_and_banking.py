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

