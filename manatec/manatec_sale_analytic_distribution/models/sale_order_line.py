from odoo import models


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "analytic.distribution.display.mixin"]
