# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    auto_account_creation = fields.Boolean(compute="_compute_auto_account_creation")
    debitor_number = fields.Char(company_dependent=True)
    creditor_number = fields.Char(company_dependent=True)

    def _compute_auto_account_creation(self):
        self.auto_account_creation = self.env.company.auto_account_creation

    def action_create_receivable_account(self):
        """Create a receivable account for the partner"""
        self.create_accounts(self.env.company, {"asset_receivable": True})
        return {"type": "ir.actions.act_window_close"}

    def action_create_payable_account(self):
        """Create a payable account for the partner"""
        self.create_accounts(self.env.company, {"liability_payable": True})
        return {"type": "ir.actions.act_window_close"}

    def create_accounts(self, company, types=None):
        """Create accounts for the partner"""
        if not self.auto_account_creation:
            return {}
        account_obj = self.env["account.account"]
        partner = self
        if self.parent_id:
            partner = self.parent_id
        values = self.get_accounts(company, partner, types)
        receivable_account_id = payable_account_id = False
        receivable_account_vals = values.pop("receivable_account_vals")
        payable_account_vals = values.pop("payable_account_vals")
        if receivable_account_vals:
            receivable_account_id = account_obj.sudo().create(receivable_account_vals)
            values["property_account_receivable_id"] = receivable_account_id.id
        if payable_account_vals:
            payable_account_id = account_obj.sudo().create(payable_account_vals)
            values["property_account_payable_id"] = payable_account_id.id
        partner.write(values)
        return values

    def get_accounts(self, company, partner, types=None):
        """Get values for the accounts"""
        if not types:
            types = {}
        debitor_vals = self._prepare_debitor_vals(company, types)
        creditor_vals = self._prepare_creditor_vals(company, types)
        values = {**debitor_vals, **creditor_vals}
        return values

    def _prepare_debitor_vals(self, company, types):
        """Prepare values for the debitor account"""
        values = {
            "debitor_number": self.debitor_number,
            "receivable_account_vals": {},
        }
        sequence_id = self.env.company.receivable_sequence_id
        if not values["debitor_number"] and types.get("asset_receivable"):
            values["debitor_number"] = sequence_id.next_by_id()
            if company.use_separate_accounts:
                template = company.receivable_template_id
                code = values["debitor_number"]
                values["receivable_account_vals"] = self._prepare_account_vals(
                    company, template, code
                )
        return values

    def _prepare_creditor_vals(self, company, types):
        """Prepare values for the creditor account"""
        values = {
            "creditor_number": self.creditor_number,
            "payable_account_vals": {},
        }
        sequence_id = self.env.company.payable_sequence_id
        if not values["creditor_number"] and types.get("liability_payable"):
            values["creditor_number"] = sequence_id.next_by_id()
            if company.use_separate_accounts:
                template = company.payable_template_id
                code = values["creditor_number"]
                values["payable_account_vals"] = self._prepare_account_vals(
                    company, template, code
                )
        return values

    def _prepare_account_vals(self, company, template, code):
        """Prepare values for the account"""
        company = self.env.company
        return {
            "name": self.name,
            "currency_id": template.currency_id.id,
            "code": code,
            "account_type": template.account_type,
            "reconcile": template.reconcile,
            "tax_ids": [(6, 0, template.tax_ids.ids)],
            "company_ids": [(6, 0, [company.id])],
            "tag_ids": [(6, 0, template.tag_ids.ids)],
            "group_id": template.group_id.id,
        }
