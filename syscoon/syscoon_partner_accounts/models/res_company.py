# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    auto_account_creation = fields.Boolean(default=True)
    receivable_sequence_id = fields.Many2one(
        "ir.sequence",
        "Receivable Sequence",
        domain=[("code", "=", "partner.auto.receivable")],
    )
    payable_sequence_id = fields.Many2one(
        "ir.sequence",
        "Payable Sequence",
        domain=[("code", "=", "partner.auto.payable")],
    )
    receivable_template_id = fields.Many2one(
        "account.account",
        "Receivable Account Template",
        domain=[("account_type", "=", "asset_receivable")],
    )
    payable_template_id = fields.Many2one(
        "account.account",
        "Payable Account Template",
        domain=[("account_type", "=", "liability_payable")],
    )
    use_separate_accounts = fields.Boolean()
    add_number_to_partner_number = fields.Boolean(
        string="Copy Debitor/Creditor to Customer/Supplier",
        help="When Debitor or Creditor number is created, automatically copy to Customer or Supplier number",
        default=True,
    )

    def _get_partner_account_types(self, account_type=None):
        """Extend to add account separation config.

        Args:
            account_type: 'receivable' or 'payable'

        Returns:
            dict with keys: asset_receivable/liability_payable, separate_accounts
        """
        types = super()._get_partner_account_types(account_type=account_type)

        if types:
            types["separate_accounts"] = bool(self.use_separate_accounts)
            types["separate_numbers"] = not self.add_number_to_partner_number

        return types
