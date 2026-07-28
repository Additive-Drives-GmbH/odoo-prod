# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        result = super()._post(soft=soft)

        company = self.env.company
        create_numbers = [auto.code for auto in company.create_auto_number_on]
        if not create_numbers:
            return result

        for move in self:
            partner = move.partner_id.commercial_partner_id
            if not partner:
                continue

            types = {}
            if (
                move.move_type in ("out_invoice", "out_refund")
                and "invoice_customer" in create_numbers
            ):
                types.update({"customer_number": True})
            elif (
                move.move_type in ("in_invoice", "in_refund")
                and "invoice_supplier" in create_numbers
            ):
                types.update({"supplier_number": True})

            if types:
                partner._create_numbers(company, types)

        return result
