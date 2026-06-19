# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    create_auto_account_on = fields.Many2many(
        "syscoon.accounts.automatic.mode",
        help="Select where the Accounts should be created. If on creating an invoice "
        "no account exists, it will created it then.",
    )

    def _get_partner_account_types(self, account_type=None, trigger=None):
        """Extend to check if automatic creation is enabled for this trigger.

        Args:
            account_type: 'receivable' or 'payable'
            trigger: One of: 'partner_customer', 'partner_supplier',
                     'invoice_customer', 'invoice_supplier',
                     'sale_order_customer', 'purchase_order_supplier'

        Returns:
            Empty dict if trigger not enabled, otherwise parent result
        """
        if trigger:
            create_accounts = [auto.code for auto in self.create_auto_account_on]
            if trigger not in create_accounts:
                return {}

        return super()._get_partner_account_types(account_type=account_type)
