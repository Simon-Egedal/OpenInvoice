from abc import ABC, abstractmethod

class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, document: bytes)->str: ...
class PaddleOCRProvider(OCRProvider):
    async def extract_text(self, document: bytes)->str: raise NotImplementedError("Optional OCR dependency is not installed")
class InvoiceExtractionProvider(ABC):
    @abstractmethod
    async def extract_invoice_fields(self, text: str)->dict: ...

