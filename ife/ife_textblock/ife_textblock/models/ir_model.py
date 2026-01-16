from odoo import fields, models


class IrModel(models.Model):
    _inherit = "ir.model"

    color = fields.Integer("Color Index")
