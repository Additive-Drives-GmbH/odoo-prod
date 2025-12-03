from odoo import models


class RepairOrder(models.Model):
    _inherit = [
        "repair.order",
        "textblock.item.mixin",
    ]
    _name = "repair.order"
