# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    shorthand = fields.Char(string='Shorthand')


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    shorthand = fields.Char(related='employee_id.shorthand', readonly=True)
