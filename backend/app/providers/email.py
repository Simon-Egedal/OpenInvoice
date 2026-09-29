from abc import ABC, abstractmethod
from email.message import EmailMessage
import logging
import smtplib
from app.core.config import settings

logger=logging.getLogger(__name__)
class EmailProvider(ABC):
    @abstractmethod
    async def send_invoice(self, recipient: str, subject: str, body: str, pdf: bytes, filename: str)->str|None: ...
class ConsoleEmailProvider(EmailProvider):
    async def send_invoice(self, recipient, subject, body, pdf, filename):
        logger.info("Development email recipient=%s subject=%s attachment=%s bytes=%d",recipient,subject,filename,len(pdf)); return "console"
class SMTPEmailProvider(EmailProvider):
    async def send_invoice(self, recipient, subject, body, pdf, filename):
        message=EmailMessage(); message["From"]=settings.smtp_from; message["To"]=recipient; message["Subject"]=subject; message.set_content(body); message.add_attachment(pdf,maintype="application",subtype="pdf",filename=filename)
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=20) as server:
            if settings.smtp_use_tls: server.starttls()
            if settings.smtp_username: server.login(settings.smtp_username,settings.smtp_password)
            server.send_message(message)
        return None
def email_provider()->EmailProvider: return SMTPEmailProvider() if settings.email_provider=="smtp" else ConsoleEmailProvider()

