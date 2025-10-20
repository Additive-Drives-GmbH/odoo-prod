# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import models


class SaleOrder(models.Model):
    """Extend sale.order with customer number"""

    _inherit = "sale.order"

    def action_confirm(self):
        company = self.env.company
        res = super().action_confirm()

        if company.allow_account_number_report:
            create_numbers = [auto.code for auto in company.create_auto_number_on]
            if "so_customer" in create_numbers:
                context = self._context.copy()
                order = self
                if not order and context.get("params"):
                    order = self.browse([context["params"].get("id")])
                partner = order.partner_id.commercial_partner_id
                partner.action_create_custmer_number()

        return res
