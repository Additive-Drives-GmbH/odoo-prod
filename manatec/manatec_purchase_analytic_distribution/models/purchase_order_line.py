# -*- coding: utf-8 -*-
"""
    Author: Denis Orechov (denis.orechov@manatec.de)
    Copyright: 2026, manaTec GmbH
    Date created: 27.07.2026
"""

from odoo import models


class PurchaseOrderLine(models.Model):
    _name = "purchase.order.line"
    _inherit = ["purchase.order.line", "analytic.distribution.display.mixin"]
