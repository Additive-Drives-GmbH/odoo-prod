import io

import pikepdf
from odoo import models


class SyscoonFinanceinterface(models.Model):
    _inherit = "syscoon.financeinterface"

    def _get_pdf_data(self, attachments):
        pdf_datas = super()._get_pdf_data(attachments)
        pdf_datas = [self._decrypt_pdf(pdf_data) for pdf_data in pdf_datas]
        return pdf_datas

    def _decrypt_pdf(self, pdf_bytes):
        """Decrypt PDF if possible using pikepdf (supports AES)."""
        try:
            with pikepdf.open(io.BytesIO(pdf_bytes), password="") as pdf:
                output = io.BytesIO()
                pdf.save(output)
                return output.getvalue()
        except pikepdf._qpdf.PasswordError:
            # Could not decrypt, return original
            return pdf_bytes
        except Exception:
            return pdf_bytes
