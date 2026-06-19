# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        company = self.env.company
        types = company._get_partner_account_types(
            account_type="payable", trigger="purchase_order_supplier"
        )
        if types:
            partner = self.partner_id.commercial_partner_id
            partner.create_accounts(company, types)
        return super().button_confirm()
