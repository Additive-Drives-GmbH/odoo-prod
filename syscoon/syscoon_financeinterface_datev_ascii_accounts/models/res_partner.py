# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    datev_exported = fields.Selection(
        selection=[("false", "False"), ("true", "True")],
        string="Exported to DATEV",
        default="false",
        company_dependent=True,
    )

    def write(self, values):
        if not values.get("datev_exported"):
            values["datev_exported"] = "false"
        return super().write(values)

    def _get_partner_email(self):
        invoice_contacts = self.commercial_partner_id.child_ids.filtered(
            lambda c: c.type == "invoice"
        )
        if invoice_contacts:
            return invoice_contacts[:1].email
        return self.email
