# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

import base64
import logging
import re

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Module constants
CLEAN_NUMBER_PATTERN = re.compile(r"\w+")  # Pattern for cleaning invoice numbers


class SyscoonFinanceinterfaceItem(models.Model):
    """DATEV XML specific implementation for export items.

    Inherits from syscoon.financeinterface.item and provides
    XML-specific processing logic.
    """

    _inherit = "syscoon.financeinterface.item"

    def process_item(self):
        """Process this export item for DATEV XML export.

        Generates XML and PDF files for the move and attaches them directly.
        """
        self.ensure_one()

        if self.state != "pending":
            return

        try:
            self.write({"state": "processing"})
            export = self.export_id

            # Process files in memory - returns list of (filename, raw_bytes)
            attachments_data = self._get_move_documents(export)

            # Write directly to working ZIP from raw bytes (skip base64 cycle)
            if attachments_data and export.mode == "datev_xml":
                export._append_raw_to_working_zip(attachments_data)

            # Create attachments for record keeping
            created_attachments = self.env["ir.attachment"]
            for name, content in attachments_data:
                attachment = self._create_attachment(name, content)
                created_attachments += attachment

            self._mark_completed(created_attachments)

            # Commit the transaction to save the "completed" state
            self.env.cr.commit()  # pylint: disable=invalid-commit

        except Exception as e:
            self._handle_processing_error(e)
            # Commit the transaction to save the "failed" state
            self.env.cr.commit()  # pylint: disable=invalid-commit

        # Check for finalization outside the item processing transaction
        self._check_and_finalize()

    def _get_move_documents(self, export):
        """Generate XML and PDF content for the move."""
        move = self.move_id
        documents = []
        is_bedi = export.xml_mode == "bedi"
        is_xrechnung = export.xml_mode == "x-rechnungen"

        # Generate XML (skip validation for BEDI mode)
        vals = export.generate_export_invoices(export.xml_mode, move)

        if not vals.get("moves_ok"):
            error_msg = vals.get("error_str", _("Failed to generate XML for move"))
            raise UserError(error_msg)

        clean_number = "".join(CLEAN_NUMBER_PATTERN.findall(move.name or ""))
        if not clean_number:
            clean_number = str(move.id)

        # Only add XML if not BEDI mode (BEDI only needs PDF + document.xml later)
        if not is_bedi:
            move_xml = vals["move_xmls"][0] if vals["move_xmls"] else None
            if not move_xml:
                raise UserError(_("No XML generated for move"))

            xml_bytes = (
                move_xml
                if isinstance(move_xml, (bytes, bytearray))  # noqa: UP038
                else move_xml.encode("utf-8")
            )
            documents.append((f"{clean_number}.xml", xml_bytes))

        # DV19-00056: X-Rechnungen export only includes XML, skip PDF generation
        if not is_xrechnung:
            # Generate PDF
            single_pdf, pdf_errors = export.get_invoice_pdf(move)
            if pdf_errors or not single_pdf:
                raise UserError(pdf_errors or _("Failed to generate PDF"))

            # Prepare PDF content
            pdf_content = single_pdf.content
            if not pdf_content:
                raise UserError(_("Failed to generate PDF content"))

            pdf_bytes = (
                pdf_content
                if isinstance(pdf_content, (bytes, bytearray))  # noqa: UP038
                else bytes(pdf_content)
            )
            documents.append((f"{clean_number}.pdf", pdf_bytes))

        return documents

    def _create_attachment(self, filename, content):
        """Create an attachment for the generated document."""
        if isinstance(content, str):
            content = content.encode("utf-8")

        return self.env["ir.attachment"].create(
            {
                "name": filename,
                "res_model": self._name,
                "res_id": self.id,
                "type": "binary",
                "datas": base64.b64encode(content),
            }
        )

    def _check_and_finalize(self):
        """Check if all items are processed and finalize if needed."""
        remaining_items = self.export_id.item_ids.filtered(
            lambda x: x.state in ["pending", "processing"]
        )
        if not remaining_items:
            self.export_id._finalize_export()
