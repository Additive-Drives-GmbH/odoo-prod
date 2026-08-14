# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "syscoon", "-at_install")
class TestLeistungsdatum(AccountTestInvoicingCommon):
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
            }
        )

    def _create_move(self, date, invoice_date):
        return (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "move_type": "entry",
                    "date": fields.Date.from_string(date),
                    "invoice_date": fields.Date.from_string(invoice_date),
                    "line_ids": [
                        (
                            0,
                            None,
                            {
                                "name": "debit line",
                                "account_id": self.company_data[
                                    "default_account_expense"
                                ].id,
                                "debit": 1000.0,
                                "credit": 0.0,
                            },
                        ),
                        (
                            0,
                            None,
                            {
                                "name": "credit line",
                                "account_id": self.company_data[
                                    "default_account_payable"
                                ].id,
                                "debit": 0.0,
                                "credit": 1000.0,
                            },
                        ),
                    ],
                }
            )
        )

    def _get_export_data(self, line):
        interface = self.env["syscoon.financeinterface"]
        export = interface.export_template()
        return {
            "interface": interface,
            "template": False,
            "lines": {
                line.id: {
                    "move": line.move_id,
                    "datev_move": line.move_id,
                    "export": export,
                }
            },
            "grouped_lines": [],
        }

    def test_leistungsdatum_set_when_dates_differ(self):
        """When bill date and accounting date differ, Leistungsdatum gets
        the accounting date and Belegdatum gets the bill date."""
        move = self._create_move("2026-05-31", "2026-06-01")
        line = move.line_ids[0]
        data = self._get_export_data(line)
        line._apply_belegdatum(data)
        export = data["lines"][line.id]["export"]
        self.assertEqual(export["Leistungsdatum"], "31052026")
        self.assertEqual(export["Belegdatum"], "0106")

    def test_leistungsdatum_empty_when_dates_equal(self):
        """When bill date equals accounting date, Leistungsdatum stays empty."""
        move = self._create_move("2026-05-31", "2026-05-31")
        line = move.line_ids[0]
        data = self._get_export_data(line)
        line._apply_belegdatum(data)
        export = data["lines"][line.id]["export"]
        self.assertEqual(export["Leistungsdatum"], "")
        self.assertEqual(export["Belegdatum"], "3105")
