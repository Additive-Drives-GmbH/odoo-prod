# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("syscoon")
class TestAccountAnalyticPlan(TransactionCase):
    def setUp(self):
        _logger.info("========== START TestAccountAnalyticPlan ==========")
        super().setUp()
        self.analytic_plan_kost1 = self.env["account.analytic.plan"].create(
            {
                "name": "Analytic Plan kost1",
                "company_id": self.env.company.id,
                "default_applicability": "optional",
                "datev_cost_center": "add_to_kost1",
            }
        )
        self.analytic_plan_kost2 = self.env["account.analytic.plan"].create(
            {
                "name": "Analytic Plan kost2",
                "company_id": self.env.company.id,
                "default_applicability": "optional",
                "datev_cost_center": "add_to_kost2",
            }
        )
        _logger.info("========== Done test_onchange_datev_cost_center ==========")
