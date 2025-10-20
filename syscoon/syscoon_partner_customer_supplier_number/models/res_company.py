# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    allow_account_number_report = fields.Boolean(string="Allow In Reports", default=False)
    customer_number_sequence_id = fields.Many2one(
        "ir.sequence",
        domain=[("code", "=", "partner.auto.customer.number")],
    )
    supplier_number_sequence_id = fields.Many2one(
        "ir.sequence",
        domain=[("code", "=", "partner.auto.supplier.number")],
    )
    add_number_to_partner_ref = fields.Boolean()
    create_auto_number_on = fields.Many2many(
        "syscoon.numbers.automatic.mode",
        help="Select when the customer/supplier numbers should be created automatically.",
    )
