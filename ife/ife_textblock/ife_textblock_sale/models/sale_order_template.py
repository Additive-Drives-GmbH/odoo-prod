from odoo import models


class SaleOrderTemplate(models.Model):
    _inherit = [
        "sale.order.template",
        "textblock.item.mixin",
    ]
    _name = "sale.order.template"
