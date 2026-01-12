from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    contact_id = fields.Many2one(
        comodel_name="res.partner",
    )
    country_of_origin_id = fields.Many2one(
        comodel_name="res.country",
        domain="[('code', 'in', ['DE','US'])]",
    )
