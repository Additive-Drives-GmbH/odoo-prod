# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import api, models

ALLOWED_MOVE_TYPES = ["in_invoice", "out_invoice", "in_refund", "out_refund"]


class AccountMove(models.Model):
    _inherit = "account.move"

    def _update_line_accounts_for_partner(self, partner):
        """Update line accounts after creating partner accounts."""
        journal_type = self.journal_id.type
        if journal_type not in ("sale", "purchase"):
            return
        default_account_id = self._get_partner_default_account_id(partner)
        types = self._prepare_account_types()
        company = self.company_id or self.env.company
        accounts = partner.create_accounts(company, types)
        if not accounts:
            return
        for line in self.line_ids:
            if line.account_id.id != default_account_id.id:
                continue
            if journal_type == "sale" and accounts.get("property_account_receivable_id"):
                line.account_id = accounts["property_account_receivable_id"]
            if journal_type == "purchase" and accounts.get("property_account_payable_id"):
                line.account_id = accounts["property_account_payable_id"]

    def write(self, vals):
        """Handle account creation when partner changes programmatically."""
        if vals.get("partner_id"):
            for move in self:
                if move.move_type not in ALLOWED_MOVE_TYPES:
                    continue
                partner = (
                    self.env["res.partner"]
                    .browse(vals["partner_id"])
                    .commercial_partner_id
                )
                move._update_line_accounts_for_partner(partner)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Handle account creation on invoice creation."""
        records = super().create(vals_list)
        for move in records:
            if move.move_type not in ALLOWED_MOVE_TYPES:
                continue
            partner = move.partner_id.commercial_partner_id
            if not partner:
                continue
            move._update_line_accounts_for_partner(partner)
        return records

    def _get_partner_default_account_id(self, partner):
        if self.move_type in ["out_invoice", "out_refund"]:
            return partner.property_account_receivable_id
        return partner.property_account_payable_id

    def _prepare_account_types(self):
        company = self.company_id or self.env.company
        if self.move_type in ["out_invoice", "out_refund"]:
            return company._get_partner_account_types(
                account_type="receivable", trigger="invoice_customer"
            )
        if self.move_type in ["in_invoice", "in_refund"]:
            return company._get_partner_account_types(
                account_type="payable", trigger="invoice_supplier"
            )
        return {}
