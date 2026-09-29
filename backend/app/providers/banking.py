from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

class BankingProvider(ABC):
    @abstractmethod
    async def create_authorization(self, callback_url: str) -> str: ...
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
    async def create_authorization(self, callback_url): return f"{callback_url}?code=mock-{uuid4()}"
    async def handle_callback(self, code): return {"connection_id":code,"provider":"mock"}
    async def get_accounts(self, connection_id): return [await self.get_account("mock-account-1")]
    async def get_account(self, account_id): return {"id":account_id,"name":"Business account","bank":"Nordic Bank (demo)","masked_number":"•••• 4821","currency":"DKK"}
    async def get_balances(self, account_id): return [{"amount":Decimal("48250.00"),"currency":"DKK"}]
    async def get_transactions(self, account_id):
        now=datetime.now(timezone.utc)
        return [{"id":f"mock-tx-{i}","booked_at":now-timedelta(days=i*3),"description":d,"counterparty":p,"amount":Decimal(a),"currency":"DKK","reference":ref} for i,(d,p,a,ref) in enumerate([("Invoice 2026-0042","Acme ApS","4995.00","2026-0042"),("Office supplies","Paper Shop","-842.50",None),("Cloud hosting","Example Cloud","-1299.00",None)],1)]
    async def disconnect(self, connection_id): return None

class EnableBankingProvider(BankingProvider):
    """Isolated placeholder. Implement only against verified Enable Banking API documentation."""
    async def create_authorization(self, callback_url): raise NotImplementedError("TODO: implement using the current official Enable Banking API specification")
    async def handle_callback(self, code): raise NotImplementedError("TODO: exchange callback according to documented flow")
    async def get_accounts(self, connection_id): raise NotImplementedError("TODO: implement documented accounts operation")
    async def get_account(self, account_id): raise NotImplementedError("TODO: implement documented account operation")
    async def get_balances(self, account_id): raise NotImplementedError("TODO: implement documented balances operation")
    async def get_transactions(self, account_id): raise NotImplementedError("TODO: implement documented transactions operation")
    async def disconnect(self, connection_id): raise NotImplementedError("TODO: implement documented session revocation")

