# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    auto_account_creation = fields.Boolean(compute="_compute_auto_account_creation")
    debitor_number = fields.Char(company_dependent=True)
    creditor_number = fields.Char(company_dependent=True)

    def _compute_auto_account_creation(self):
        self.auto_account_creation = self.env.company.auto_account_creation

    def action_create_receivable_account(self):
        """Create a receivable account for the partner"""
        company = self.env.company
        types = company._get_partner_account_types(account_type="receivable")
        self.create_accounts(company, types)
        return {"type": "ir.actions.act_window_close"}

    def action_create_payable_account(self):
        """Create a payable account for the partner"""
        company = self.env.company
        types = company._get_partner_account_types(account_type="payable")
        self.create_accounts(company, types)
        return {"type": "ir.actions.act_window_close"}

    def create_customer_number(self):
        company = self.env.company
        types = {"separate_numbers": True}
        return self.create_accounts(company, types)

    def create_supplier_number(self):
        company = self.env.company
        types = {"separate_numbers": True}
        return self.create_accounts(company, types)

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
        if company.add_number_to_partner_ref and not self.ref:
            values.update(
                {
                    "ref": debitor_vals["customer_number"]
                    or creditor_vals["supplier_number"]
                }
            )
        return values

    def _prepare_debitor_vals(self, company, types):
        """Prepare values for the debitor account"""
        values = {
            "debitor_number": self.debitor_number,
            "customer_number": self.customer_number,
            "receivable_account_vals": {},
        }
        sequence_id = self._get_receivable_sequence()
        if not values["debitor_number"] and types.get("asset_receivable"):
            values["debitor_number"] = sequence_id.next_by_id()
            if (
                types.get("separate_accounts")
                and "property_account_receivable_id" in self._fields
            ):
                values["receivable_account_vals"] = self._prepare_account_vals(
                    company=company,
                    template=company.receivable_template_id,
                    code=values["debitor_number"],
                )
        # Only copy debitor→customer if add_number_to_partner_number is checked
        # (separate_numbers is False means copy is enabled)
        if (
            values["debitor_number"]
            and not values["customer_number"]
            and not types.get("separate_numbers")
        ):
            values["customer_number"] = values["debitor_number"]
        # NOTE: Removed separate number creation logic - customer_number creation
        # is now controlled solely by create_auto_number_on in
        # syscoon_partner_customer_supplier_number module
        return values

    def _prepare_creditor_vals(self, company, types):
        """Prepare values for the creditor account"""
        values = {
            "creditor_number": self.creditor_number,
            "supplier_number": self.supplier_number,
            "payable_account_vals": {},
        }
        sequence_id = self._get_payable_sequence()
        if not values["creditor_number"] and types.get("liability_payable"):
            values["creditor_number"] = sequence_id.next_by_id()
            if (
                types.get("separate_accounts")
                and "property_account_payable_id" in self._fields
            ):
                values["payable_account_vals"] = self._prepare_account_vals(
                    company=company,
                    template=company.payable_template_id,
                    code=values["creditor_number"],
                )
        # Only copy creditor→supplier if add_number_to_partner_number is checked
        # (separate_numbers is False means copy is enabled)
        if (
            values["creditor_number"]
            and not values["supplier_number"]
            and not types.get("separate_numbers")
        ):
            values["supplier_number"] = values["creditor_number"]
        # NOTE: Removed separate number creation logic - supplier_number creation
        # is now controlled solely by create_auto_number_on in
        # syscoon_partner_customer_supplier_number module
        return values

    def _prepare_customer_supplier_number_values(self, company, types):
        """Override to copy from debitor/creditor when enabled.

        Note: Does NOT call super() when copying to avoid generating unused sequences.
        """
        if company.add_number_to_partner_number:
            vals = {}
            if (
                types.get("customer_number")
                and not self.customer_number
                and self.debitor_number
            ):
                vals["customer_number"] = self.debitor_number
            if (
                types.get("supplier_number")
                and not self.supplier_number
                and self.creditor_number
            ):
                vals["supplier_number"] = self.creditor_number
            return vals
        return super()._prepare_customer_supplier_number_values(company, types)

    def _get_receivable_sequence(self):
        """Get the receivable sequence"""
        sequence_id = self.env.company.receivable_sequence_id
        if not sequence_id:
            raise UserError(
                _("No receivable sequence defined for company %s", self.env.company.name)
            )
        return sequence_id

    def _get_payable_sequence(self):
        """Get the payable sequence"""
        sequence_id = self.env.company.payable_sequence_id
        if not sequence_id:
            raise UserError(
                _("No payable sequence defined for company %s", self.env.company.name)
            )
        return sequence_id

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
