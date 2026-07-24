from odoo import models


class PurchaseOrderLine(models.Model):
    _name = "purchase.order.line"
    _inherit = ["purchase.order.line", "analytic.distribution.display.mixin"]
