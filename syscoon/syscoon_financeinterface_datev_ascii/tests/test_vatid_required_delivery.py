# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "syscoon", "-at_install")
class TestVatIdRequiredDelivery(AccountTestInvoicingCommon):
    """A ``datev_vatid_required`` account must accept the VAT-ID coming from
    the delivery address (``partner_shipping_id``), mirroring the export
    logic in ``generate_export_line``.

    Reproduces AP19-00106-4 (Issue 2): a German customer without a VAT-ID
    ships to an EU partner that has a valid VAT-ID. The intra-Community
    fiscal position routes the revenue to an account with
    ``datev_vatid_required=True`` (e.g. SKR04 4125 / 4336). The DATEV
    pre-posting check refused to post because it only inspected the
    invoice partner's VAT, even though the delivery partner's VAT is the
    one actually written to the DATEV export.
    """

    chart_template = "de_skr03"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.write({"export_finance_interface": "datev_ascii"})

        cls.vatid_account = cls.company_data["default_account_revenue"].copy(
            {"datev_vatid_required": True}
        )
        cls.balance_account = cls.company_data["default_account_expense"]

        cls.customer_no_vat = cls.env["res.partner"].create(
            {"name": "DE customer no VAT", "country_id": cls.env.ref("base.de").id}
        )
        cls.delivery_with_vat = cls.env["res.partner"].create(
            {
                "name": "EU delivery with VAT",
                "country_id": cls.env.ref("base.be").id,
                "vat": "BE0477472701",
            }
        )

    def _make_move(self, shipping_partner):
        """Journal entry with one line on the VAT-ID-required account, billed
        to a partner with no VAT, shipping to ``shipping_partner``."""
        move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "move_type": "entry",
                    "date": fields.Date.from_string("2026-05-15"),
                    "partner_id": self.customer_no_vat.id,
                    "partner_shipping_id": shipping_partner.id,
                    "line_ids": [
                        (
                            0,
                            None,
                            {
                                "name": "Goods",
                                "account_id": self.vatid_account.id,
                                "partner_id": self.customer_no_vat.id,
                                "debit": 1000.0,
                                "credit": 0.0,
                            },
                        ),
                        (
                            0,
                            None,
                            {
                                "name": "Balance",
                                "account_id": self.balance_account.id,
                                "partner_id": self.customer_no_vat.id,
                                "debit": 0.0,
                                "credit": 1000.0,
                            },
                        ),
                    ],
                }
            )
        )
        return move

    def _vatid_errors(self, move):
        return [e for e in move.line_ids._prepare_datev_errors() if "VAT-ID" in e]

    def test_delivery_vat_satisfies_requirement(self):
        """Delivery partner carries a VAT-ID → no VAT-ID error even though
        the invoice partner has none."""
        move = self._make_move(self.delivery_with_vat)
        self.assertFalse(
            self._vatid_errors(move),
            "The delivery address VAT-ID must satisfy datev_vatid_required.",
        )

    def test_no_vat_anywhere_still_errors(self):
        """When neither the invoice partner nor the delivery address has a
        VAT-ID, the check must still raise (regression guard)."""
        move = self._make_move(self.customer_no_vat)
        self.assertTrue(
            self._vatid_errors(move),
            "Missing VAT-ID on every partner must still be reported.",
        )
