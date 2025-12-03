from odoo import models


class StockPicking(models.Model):
    _inherit = [
        "stock.picking",
        "textblock.item.mixin",
    ]
    _name = "stock.picking"
