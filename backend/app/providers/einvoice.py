from abc import ABC, abstractmethod
class EInvoiceProvider(ABC):
    @abstractmethod
    async def parse(self, document: bytes)->dict: ...

