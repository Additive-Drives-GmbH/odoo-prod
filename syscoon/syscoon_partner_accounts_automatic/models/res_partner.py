# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        """Inherit to create accounts for partners"""
        records = super().create(vals_list)
        company = self.env.company
        for res in records:
            types = res._prepare_account_types()
            if not types:
                continue
            res.create_accounts(company, types)
        return records

    def _prepare_account_types(self):
        """Prepare the account types for the partner"""
        company = self.env.company
        if self.commercial_partner_id.id != self.id:
            return {}

        types = {}
        receivable = company._get_partner_account_types(
            account_type="receivable", trigger="partner_customer"
        )
        payable = company._get_partner_account_types(
            account_type="payable", trigger="partner_supplier"
        )

        if receivable:
            types.update(receivable)
        if payable:
            types.update(payable)

        return types
