# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    allow_account_number_report = fields.Boolean(
        related="company_id.allow_account_number_report", readonly=False
    )
    customer_number_sequence_id = fields.Many2one(
        "ir.sequence",
        related="company_id.customer_number_sequence_id",
        readonly=False,
        domain=[("code", "=", "partner.auto.customer.number")],
    )
    supplier_number_sequence_id = fields.Many2one(
        "ir.sequence",
        related="company_id.supplier_number_sequence_id",
        readonly=False,
        domain=[("code", "=", "partner.auto.supplier.number")],
    )
    add_number_to_partner_ref = fields.Boolean(
        related="company_id.add_number_to_partner_ref", readonly=False
    )
    create_auto_number_on = fields.Many2many(
        "syscoon.numbers.automatic.mode",
        related="company_id.create_auto_number_on",
        readonly=False,
        help="Select when customer/supplier numbers should be created. Please notice, "
        "without a selection no numbers will be created automatically.",
    )

    def action_create_customer_sequence(self):
        """Add a customer sequence to the company"""
        self.ensure_one()
        sequence = self._create_sequence("partner.auto.customer.number", 100000)
        self.update({"customer_number_sequence_id": sequence.id})

    def action_create_supplier_sequence(self):
        """Add a supplier sequence to the company"""
        self.ensure_one()
        sequence = self._create_sequence("partner.auto.supplier.number", 700000)
        self.update({"supplier_number_sequence_id": sequence.id})

    def _create_sequence(self, code, number_next):
        """Create a sequence"""
        self.ensure_one()
        sequence = self.env["ir.sequence"].create(
            {
                "name": f"{self.env.company.name} {code}",
                "code": code,
                "number_next": number_next,
                "company_id": self.env.company.id,
            }
        )
        return sequence
