# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountAnalyticPlan(models.Model):
    _inherit = "account.analytic.plan"

    datev_cost_center = fields.Selection(
        selection=[
            ("add_to_kost1", "add to Datev KOST1"),
            ("add_to_kost2", "add to Datev KOST2"),
        ]
    )
