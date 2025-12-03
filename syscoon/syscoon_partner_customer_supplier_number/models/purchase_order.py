# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import models


class PurchaseOrder(models.Model):
    """Extend purchase.order with supplier number"""

    _inherit = "purchase.order"

    def button_confirm(self):
        """Extend the confirm button to create a supplier number"""
        company = self.env.company

        if company.allow_account_number_report:
            create_numbers = [auto.code for auto in company.create_auto_number_on]
            if "po_supplier" in create_numbers:
                partner = self.partner_id.commercial_partner_id
                partner.action_create_supplier_number()

        return super().button_confirm()
