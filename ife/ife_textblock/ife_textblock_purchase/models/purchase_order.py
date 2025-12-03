from odoo import models


class PurchaseOrder(models.Model):
    _inherit = [
        "purchase.order",
        "textblock.item.mixin",
    ]
    _name = "purchase.order"
