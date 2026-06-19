# © 2026 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged


@tagged("post_install", "syscoon", "-at_install")
class TestReverseCreditDebit(AccountTestInvoicingCommon):
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
        cls.test_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string("2024-01-01"),
                "line_ids": [
                    (
                        0,
                        None,
                        {
                            "name": "debit line",
                            "account_id": cls.company_data["default_account_revenue"].id,
                            "debit": 1000.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        None,
                        {
                            "name": "credit line",
                            "account_id": cls.company_data["default_account_expense"].id,
                            "debit": 0.0,
                            "credit": 1000.0,
                        },
                    ),
                ],
            }
        )

    def _get_export_data(self, line):
        interface = self.env["syscoon.financeinterface"]
        export = interface.export_template()
        data = {
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
        return data

    def test_kennzeichen_default_debit(self):
        """Debit line gets 'S' when reverse is disabled."""
        self.company.datev_reverse_credit_debit = False
        debit_line = self.test_move.line_ids.filtered(lambda l: l.debit)
        data = self._get_export_data(debit_line)
        debit_line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Soll/Haben-Kennzeichen"],
            "S",
        )

    def test_kennzeichen_default_credit(self):
        """Credit line gets 'H' when reverse is disabled."""
        self.company.datev_reverse_credit_debit = False
        credit_line = self.test_move.line_ids.filtered(lambda l: l.credit)
        data = self._get_export_data(credit_line)
        credit_line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][credit_line.id]["export"]["Soll/Haben-Kennzeichen"],
            "H",
        )

    def test_kennzeichen_reversed_debit(self):
        """Debit line gets 'H' when reverse is enabled."""
        self.company.datev_reverse_credit_debit = True
        debit_line = self.test_move.line_ids.filtered(lambda l: l.debit)
        data = self._get_export_data(debit_line)
        debit_line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Soll/Haben-Kennzeichen"],
            "H",
        )

    def test_kennzeichen_reversed_credit(self):
        """Credit line gets 'S' when reverse is enabled."""
        self.company.datev_reverse_credit_debit = True
        credit_line = self.test_move.line_ids.filtered(lambda l: l.credit)
        data = self._get_export_data(credit_line)
        credit_line._apply_kennzeichen(data)
        self.assertEqual(
            data["lines"][credit_line.id]["export"]["Soll/Haben-Kennzeichen"],
            "S",
        )

    def test_konto_default(self):
        """Konto/Gegenkonto are not swapped when reverse is disabled."""
        self.company.datev_reverse_credit_debit = False
        debit_line = self.test_move.line_ids.filtered(lambda l: l.debit)
        data = self._get_export_data(debit_line)
        debit_line._apply_konto(data)
        account_code = debit_line.account_id.code
        counterpart_code = self.test_move.export_account_counterpart.code
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Konto"],
            account_code,
        )
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Gegenkonto (ohne BU-Schlüssel)"],
            counterpart_code,
        )

    def test_konto_reversed(self):
        """Konto/Gegenkonto are swapped when reverse is enabled."""
        self.company.datev_reverse_credit_debit = True
        debit_line = self.test_move.line_ids.filtered(lambda l: l.debit)
        data = self._get_export_data(debit_line)
        debit_line._apply_konto(data)
        account_code = debit_line.account_id.code
        counterpart_code = self.test_move.export_account_counterpart.code
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Konto"],
            counterpart_code,
        )
        self.assertEqual(
            data["lines"][debit_line.id]["export"]["Gegenkonto (ohne BU-Schlüssel)"],
            account_code,
        )

    def test_company_field_default_false(self):
        """The reverse credit/debit field defaults to False."""
        new_company = self.env["res.company"].create({"name": "Test Co"})
        self.assertFalse(new_company.datev_reverse_credit_debit)

    def test_config_settings_field(self):
        """Settings field correctly reads/writes the company field."""
        self.company.datev_reverse_credit_debit = False
        settings = self.env["res.config.settings"].with_company(self.company).create({})
        self.assertFalse(settings.company_datev_reverse_credit_debit)
        settings.company_datev_reverse_credit_debit = True
        settings.flush_recordset()
        self.assertTrue(self.company.datev_reverse_credit_debit)
