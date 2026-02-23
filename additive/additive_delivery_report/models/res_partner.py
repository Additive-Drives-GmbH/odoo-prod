from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    purchase_order_no = fields.Char(
        string="Purchase Order Number",
    )
    supplier_no = fields.Char()
