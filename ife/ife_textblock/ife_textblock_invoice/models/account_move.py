from odoo import models


class AccountMove(models.Model):
    _inherit = [
        "account.move",
        "textblock.item.mixin",
    ]
    _name = "account.move"
