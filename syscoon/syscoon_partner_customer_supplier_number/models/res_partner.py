# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ResPartner(models.Model):
    """Extend res.partner with customer and supplier number"""

    _inherit = "res.partner"

    customer_number = fields.Char(company_dependent=True)
    supplier_number = fields.Char(company_dependent=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Inherit to create numbers for partners"""
        records = super().create(vals_list)
        company = self.env.company
        create_numbers = [auto.code for auto in company.create_auto_number_on]

        for res in records:
            # Skip if not a commercial partner (contact of a company)
            if res.commercial_partner_id.id != res.id:
                continue

            types = {}
            if "partner_customer" in create_numbers:
                types.update({"customer_number": True})
            if "partner_supplier" in create_numbers:
                types.update({"supplier_number": True})

            if types:
                res._create_numbers(company, types)
        return records

    def action_create_custmer_number(self):
        """Create a customer number for the partner"""
        self._create_numbers(self.env.company, {"customer_number": True})
        return {"type": "ir.actions.act_window_close"}

    def action_create_supplier_number(self):
        """Create a supplier number for the partner"""
        self._create_numbers(self.env.company, {"supplier_number": True})
        return {"type": "ir.actions.act_window_close"}

    def _create_numbers(self, company, types=None):
        """Write the customer and supplier number"""
        vals = {}
        for field_key in ["customer_number", "supplier_number"]:
            if types.get(field_key) and not self[field_key]:
                vals[field_key] = self._get_next_number(
                    company[field_key + "_sequence_id"]
                )
        if company.add_number_to_partner_ref and vals:
            vals["ref"] = self._get_ref_from_res(vals)
        if vals:
            self.write(vals)

    def _get_next_number(self, sequence):
        """Get the next number"""
        return sequence.next_by_id() if sequence else False

    def _get_ref_from_res(self, res):
        """Get the reference res"""
        if res.get("customer_number"):
            return res["customer_number"]
        if res.get("supplier_number"):
            return res["supplier_number"]
        return ""
