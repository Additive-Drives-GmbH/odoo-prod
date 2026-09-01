# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    buyer_id = fields.Many2one('res.partner', string='Buyer')
    buyer_email = fields.Char(string='Buyer Email', compute='_compute_buyer_email', store=True)

    @api.depends('buyer_id', 'buyer_id.email')
    def _compute_buyer_email(self):
        for lead in self:
            lead.buyer_email = lead.buyer_id.email
