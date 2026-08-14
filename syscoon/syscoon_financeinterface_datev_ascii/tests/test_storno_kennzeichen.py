# © 2026 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "syscoon", "-at_install")
class TestStornoKennzeichen(AccountTestInvoicingCommon):
    """With Odoo's storno accounting the reversal keeps the account on the
    side of the original booking and negates the amount (core
    ``_compute_debit_credit``). The DATEV export has to report the economic
    side, so a negative credit becomes 'S' and a negative debit becomes 'H'."""

    chart_template = "de_skr03"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.write(
            {
                "export_finance_interface": "datev_ascii",
                "datev_export_method": "net",
                "datev_voucher_date_format": "%d%m",
                "datev_account_code_digits": 4,
                "account_storno": True,
            }
        )
        cls.invoice = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            invoice_date=fields.Date.from_string("2026-01-01"),
            amounts=[100.0],
            taxes=cls.tax_sale_a,
            post=True,
        )
        cls.storno_refund = cls.invoice._reverse_moves()
        cls.storno_refund.action_post()

    def _revenue_line(self):
        return self.storno_refund.line_ids.filtered(
            lambda l: l.account_id.account_type == "income"
        )

    def _receivable_line(self):
        return self.storno_refund.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )

    def _get_export_data(self, line):
        interface = self.env["syscoon.financeinterface"]
        return {
            "interface": interface,
            "template": False,
            "lines": {
                line.id: {
                    "move": line.move_id,
                    "datev_move": line.move_id,
                    "export": interface.export_template(),
                }
            },
            "grouped_lines": [],
        }

    def test_storno_refund_books_negative_amounts(self):
        """Guard: the reversal really is booked storno."""
        revenue_line = self._revenue_line()
        receivable_line = self._receivable_line()
        self.assertTrue(self.storno_refund.is_storno)
        self.assertLess(revenue_line.credit, 0.0)
        self.assertGreater(revenue_line.balance, 0.0)
        self.assertLess(receivable_line.debit, 0.0)
        self.assertLess(receivable_line.balance, 0.0)

    def test_kennzeichen_storno_negative_credit_is_soll(self):
        """A storno line booked as negative credit is exported as 'S'."""
        line = self._revenue_line()
        data = self._get_export_data(line)
        line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][line.id]["export"]["Soll/Haben-Kennzeichen"],
            "S",
        )

    def test_kennzeichen_storno_negative_debit_is_haben(self):
        """A storno line booked as negative debit is exported as 'H'."""
        line = self._receivable_line()
        data = self._get_export_data(line)
        line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][line.id]["export"]["Soll/Haben-Kennzeichen"],
            "H",
        )

    def test_kennzeichen_storno_respects_reverse_credit_debit(self):
        """The reverse credit/debit setting still inverts the storno side."""
        self.company.datev_reverse_credit_debit = True
        line = self._revenue_line()
        data = self._get_export_data(line)
        line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][line.id]["export"]["Soll/Haben-Kennzeichen"],
            "H",
        )

    def test_kennzeichen_storno_line_follows_company_setting(self):
        """The storno accounting setting is the switch: with it switched off the
        same booked line is reported by its debit/credit field again, so the
        negative credit of the storno credit note becomes 'H'."""
        self.company.account_storno = False
        line = self._revenue_line()
        self.assertLess(line.credit, 0.0)
        data = self._get_export_data(line)
        line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][line.id]["export"]["Soll/Haben-Kennzeichen"],
            "H",
        )

    def test_kennzeichen_without_storno_accounting_is_unchanged(self):
        """The same credit note booked without storno also exports 'S'."""
        self.company.account_storno = False
        refund = self.invoice._reverse_moves()
        refund.action_post()
        line = refund.line_ids.filtered(lambda l: l.account_id.account_type == "income")
        self.assertFalse(line.is_storno)
        self.assertGreater(line.debit, 0.0)
        data = self._get_export_data(line)
        line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][line.id]["export"]["Soll/Haben-Kennzeichen"],
            "S",
        )

    def test_export_line_of_storno_refund_is_soll_with_positive_amount(self):
        """The exported revenue line of a storno credit note is 'S' 100,00."""
        interface = self.env["syscoon.financeinterface"]
        account_code = self._revenue_line().account_id.code
        data = interface.generate_export_moves(self.storno_refund)
        revenue_lines = [
            line for line in data["grouped_lines"] if line["Konto"] == account_code
        ]
        self.assertEqual(len(revenue_lines), 1)
        self.assertEqual(revenue_lines[0]["Soll/Haben-Kennzeichen"], "S")
        self.assertEqual(revenue_lines[0]["Umsatz (ohne Soll/Haben-Kz)"], "100,00")
