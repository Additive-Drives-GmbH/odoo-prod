# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import tagged

_logger = logging.getLogger(__name__)

# from odoo.exceptions import UserError, RedirectWarning
# from odoo.addons.account.tests.test_account_move_entry import TestAccountMove


@tagged("post_install")
class TestAccountMoveFinanceInterface(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        _logger.info("========== START TestAccountMoveFinanceInterface ==========")
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.interface_config = cls.env[
            "syscoon.financeinterface.bookingtext.config"
        ].create(
            {
                "sequence": "11",
                "journal_id": cls.company_data["default_journal_bank"].id,
                "field": "move_id.ref",
            }
        )
        tax_repartition_line = cls.company_data[
            "default_tax_sale"
        ].refund_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
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
                            "name": "revenue line 1",
                            "account_id": cls.company_data["default_account_revenue"].id,
                            "debit": 500.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        None,
                        {
                            "name": "revenue line 2",
                            "account_id": cls.company_data["default_account_revenue"].id,
                            "debit": 1000.0,
                            "credit": 0.0,
                            "tax_ids": [(6, 0, cls.company_data["default_tax_sale"].ids)],
                        },
                    ),
                    (
                        0,
                        None,
                        {
                            "name": "tax line",
                            "account_id": cls.company_data["default_account_tax_sale"].id,
                            "debit": 150.0,
                            "credit": 0.0,
                            "tax_repartition_line_id": tax_repartition_line.id,
                        },
                    ),
                    (
                        0,
                        None,
                        {
                            "name": "counterpart line",
                            "account_id": cls.company_data["default_account_expense"].id,
                            "debit": 0.0,
                            "credit": 1650.0,
                        },
                    ),
                ],
            }
        )
        cls.entry_line_vals_1 = {
            "name": "Line 1",
            "account_id": cls.company_data["default_account_revenue"].id,
            "debit": 500.0,
            "credit": 0.0,
        }
        cls.entry_line_vals_2 = {
            "name": "Line 2",
            "account_id": cls.company_data["default_account_expense"].id,
            "debit": 0.0,
            "credit": 500.0,
        }
        cls.export_id = False
        _logger.info("========== DONE TestAccountMoveFinanceInterface ==========")

    def test_interface_config_computed_name(self):
        _logger.info("========== START test_interface_config_computed_name ==========")
        self.assertEqual(self.interface_config.name, "Move Reference")
        _logger.info("========== DONE test_interface_config_computed_name ==========")

    def test_show_export_to_draft_button(self):
        _logger.info("========== START test_show_export_to_draft_button ==========")
        self.assertEqual(self.test_move.show_export_to_draft_button, False)
        self.export_id = self.env["syscoon.financeinterface"].create(
            {
                "name": "Export test name",
                "mode": "none",
                "period": "2024-01-31 - 2024-12-31",
            }
        )
        self.test_move.export_id = self.export_id.id
        self.test_move._post()
        self.assertEqual(self.test_move.show_export_to_draft_button, True)
        _logger.info("========== DONE test_show_export_to_draft_button ==========")

    def test_compute_export_account_counterpart(self):
        _logger.info(
            "========== START test_compute_export_account_counterpart =========="
        )
        self.assertNotEqual(self.test_move.export_account_counterpart, False)
        _logger.info("========== DONE test_compute_export_account_counterpart ==========")
