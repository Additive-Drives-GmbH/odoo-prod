# © 2026 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
"""5000-00056: XML attachment detection blind spots in the DATEV XML export.

An e-invoice XML linked to the ``ubl_cii_xml_file`` binary field (bills
migrated from v17 or written by other e-invoice flows) is hidden from
``move.attachment_ids`` by the implicit ``res_field`` filter of
``ir.attachment._search``. XML files uploaded by users without write
access on ``ir.ui.view`` are stored with mimetype ``text/plain``
(``ir.attachment._check_contents``). Both must still be exported.
"""
import base64

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "syscoon")
class TestXRechnungenXmlDetection(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref(
            "syscoon_financeinterface.group_syscoon_financeinterface"
        )
        company = cls.company_data["company"]
        # On staging copies syscoon_partner_accounts_automatic_invoice would
        # require debitor/creditor sequences on bill creation; no-op on bare
        # DBs where the module is not installed.
        if "auto_account_creation" in company._fields:
            company.sudo().auto_account_creation = False
        cls.export = cls.env["syscoon.financeinterface"].create(
            {
                "name": "TEST X-Rechnungen Export",
                "mode": "datev_xml",
                "xml_mode": "x-rechnungen",
                "xml_invoices": "vendors",
                "start_date": fields.Date.from_string("2026-01-01"),
                "end_date": fields.Date.from_string("2026-01-31"),
            }
        )
        cls.export_standard = cls.env["syscoon.financeinterface"].create(
            {
                "name": "TEST Standard Export",
                "mode": "datev_xml",
                "xml_mode": "standard",
                "xml_invoices": "both",
                "start_date": fields.Date.from_string("2026-01-01"),
                "end_date": fields.Date.from_string("2026-01-31"),
            }
        )
        cls.vendor_bill = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.partner_a.id,
                "invoice_date": fields.Date.from_string("2026-01-15"),
                "date": fields.Date.from_string("2026-01-15"),
                "ref": "XR-001",
            }
        )

    def _create_attachment(self, name, mimetype, content=b"<xml/>"):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "res_model": "account.move",
                "res_id": self.vendor_bill.id,
                "type": "binary",
                "datas": base64.b64encode(content),
                "mimetype": mimetype,
            }
        )

    def _create_ubl_cii_field_attachment(self, content=b"<xml/>"):
        """Simulate a bill whose e-invoice XML is linked to the
        ubl_cii_xml_file binary field. Because res_field is set,
        ir.attachment._search hides it from move.attachment_ids."""
        return self.env["ir.attachment"].create(
            {
                "name": "INV_2026_00002_ubl_de.xml",
                "res_model": "account.move",
                "res_id": self.vendor_bill.id,
                "res_field": "ubl_cii_xml_file",
                "type": "binary",
                "datas": base64.b64encode(content),
                "mimetype": "text/xml",
            }
        )

    def test_xrechnungen_exports_res_field_linked_xml(self):
        """A bill whose XML is linked as ubl_cii_xml_file must be exported."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Invoice xmlns="urn:test"><ID>EINVOICE</ID></Invoice>'
        )
        self._create_ubl_cii_field_attachment(content=xml_content)
        result = self.export.generate_export_invoices("x-rechnungen", self.vendor_bill)
        self.assertIn(self.vendor_bill, result["moves_ok"])
        self.assertEqual(result["move_errors"], [])
        self.assertEqual(result["move_xmls"], [xml_content])

    def test_xrechnungen_exports_text_plain_xml_upload(self):
        """XML uploaded by a non-system user is stored as text/plain
        (ir.attachment._check_contents) and must still be detected."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Invoice xmlns="urn:test"><ID>UPLOAD</ID></Invoice>'
        )
        self._create_attachment("INV_upload.xml", "text/plain", content=xml_content)
        result = self.export.generate_export_invoices("x-rechnungen", self.vendor_bill)
        self.assertIn(self.vendor_bill, result["moves_ok"])
        self.assertEqual(result["move_errors"], [])
        self.assertEqual(result["move_xmls"], [xml_content])

    def test_standard_mode_skips_bill_with_only_res_field_xml(self):
        """Standard mode must treat a bill with only a field-linked XML as
        X-Rechnung and skip it instead of generating XML from move data."""
        self._create_ubl_cii_field_attachment()
        result = self.export_standard.generate_export_invoices(
            "standard", self.vendor_bill
        )
        self.assertIn(self.vendor_bill.id, result["move_errors"])
        self.assertIn("treated as X-Rechnung", result["error_str"])

    def test_get_existing_xml_includes_res_field_xml(self):
        """_get_existing_xml must also see the field-linked e-invoice XML."""
        att = self._create_ubl_cii_field_attachment()
        result = self.export._get_existing_xml(self.vendor_bill, "standard")
        self.assertIn(att, result)
