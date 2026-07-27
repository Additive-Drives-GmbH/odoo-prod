# -*- coding: utf-8 -*-
"""
    Author: Denis Orechov (denis.orechov@manatec.de)
    Copyright: 2026, manaTec GmbH
    Date created: 27.07.2026
"""

from odoo import models


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "analytic.distribution.display.mixin"]
