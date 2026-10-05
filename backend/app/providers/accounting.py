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
    async def export_rows(self, rows: list[dict], columns: list[str]) -> bytes:
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            # User-entered text must not become spreadsheet formulas.
            safe = {key: ("'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value) for key, value in row.items()}
            writer.writerow(safe)
        return output.getvalue().encode("utf-8-sig")
    async def get_accounts(self): return []
    async def export_invoice(self,invoice): return self._csv(invoice)
    async def export_journal_entry(self,entry): return self._csv(entry)
    def _csv(self,row):
        output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=list(row)); writer.writeheader(); writer.writerow(row); return output.getvalue().encode()
