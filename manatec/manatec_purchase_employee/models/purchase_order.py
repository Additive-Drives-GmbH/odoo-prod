# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    employee_id = fields.Many2one('hr.employee', string='Employee')

    shorthand = fields.Char(string='Shorthand', compute='_compute_shorthand', store=True, readonly=True)

    @api.depends('employee_id', 'employee_id.shorthand')
    def _compute_shorthand(self):
        for order in self:
            if order.employee_id:
                order.shorthand = order.employee_id.shorthand
            else:
                order.shorthand = False

