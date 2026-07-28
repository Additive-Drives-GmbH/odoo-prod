# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.


from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        company = self.env.company
        types = company._get_partner_account_types(
            account_type="receivable", trigger="sale_order_customer"
        )
        if types:
            partner = self.partner_id.commercial_partner_id
            partner.create_accounts(company, types)
        return res
