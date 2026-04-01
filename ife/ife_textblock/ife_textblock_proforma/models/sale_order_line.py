from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    proforma_textblock_id = fields.Many2one(
        comodel_name="text.block",
        string="Pro-forma Textblock",
    )
