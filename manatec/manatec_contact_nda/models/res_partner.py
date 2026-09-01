# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    nda_valid_until = fields.Date(string='NDA Valid Until')
