# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "syscoon")
class TestXRechnungVendorOnly(TransactionCase):
    """DV19-00056: X-Rechnungen export must only consider Vendor Bills.

    The "Invoices" field (``xml_invoices``) must effectively be locked to
    Vendor Bills when the X-Rechnungen export method is selected, so that
    customer invoices are never pulled into the export (and therefore never
    end up skipped in the export log).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.export_model = cls.env["syscoon.financeinterface"]

    def _new_xrechnung_export(self, xml_invoices):
        """Build an unsaved X-Rechnungen export with the given invoice scope."""
        return self.export_model.new(
            {
                "mode": "datev_xml",
                "xml_mode": "x-rechnungen",
                "xml_invoices": xml_invoices,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
            }
        )

    def _move_types_in_domain(self, domain):
        for clause in domain:
            # Skip logical operators ('&', '|', '!'); leaves are (field, op, value)
            if isinstance(clause, str):
                continue
            if clause[0] == "move_type":
                return set(clause[2])
        return set()

    def test_domain_forces_vendor_bills_when_invoices_is_both(self):
        """Even with xml_invoices='both', x-rechnungen yields vendor types only."""
        export = self._new_xrechnung_export("both")

        move_types = self._move_types_in_domain(export._get_move_domain())

        self.assertEqual(move_types, {"in_invoice", "in_refund"})

    def test_domain_forces_vendor_bills_when_invoices_is_customers(self):
        """Even with xml_invoices='customers', x-rechnungen excludes customer types."""
        export = self._new_xrechnung_export("customers")

        move_types = self._move_types_in_domain(export._get_move_domain())

        self.assertEqual(move_types, {"in_invoice", "in_refund"})

    def test_onchange_xml_mode_forces_vendors(self):
        """Selecting x-rechnungen forces the Invoices field to Vendor Bills."""
        export = self.export_model.new(
            {"mode": "datev_xml", "xml_mode": "x-rechnungen", "xml_invoices": "both"}
        )

        export._onchange_xml_mode()

        self.assertEqual(export.xml_invoices, "vendors")
