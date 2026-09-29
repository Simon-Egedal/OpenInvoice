from abc import ABC, abstractmethod
import csv
import io

class AccountingProvider(ABC):
    @abstractmethod
    async def get_accounts(self)->list[dict]: ...
    @abstractmethod
    async def export_invoice(self, invoice: dict)->bytes: ...
    @abstractmethod
    async def export_journal_entry(self, entry: dict)->bytes: ...
class CSVAccountingProvider(AccountingProvider):
    async def get_accounts(self): return []
    async def export_invoice(self,invoice): return self._csv(invoice)
    async def export_journal_entry(self,entry): return self._csv(entry)
    def _csv(self,row):
        output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=list(row)); writer.writeheader(); writer.writerow(row); return output.getvalue().encode()

