# -*- coding: utf-8 -*-
"""
    Author: Denis Orechov (denis.orechov@manatec.de)
    Copyright: 2026, manaTec GmbH
    Date created: 21.08.2026
"""

from odoo import fields, models


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order"]

    pre_text = fields.Html(string="Pre-Text")
