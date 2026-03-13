from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    disable_purchase_position_recompute = fields.Boolean(
        string="Do not recompute positions on purchase orders"
    )
