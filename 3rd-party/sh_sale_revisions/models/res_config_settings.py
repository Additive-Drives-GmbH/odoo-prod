# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_sale_revision = fields.Boolean("Enable Sale Revisions")
    sh_manage_chatter_history = fields.Boolean("Enable Sale Revisions")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_sale_revision = fields.Boolean("Enable Sale Revisions",
                                      related="company_id.sh_sale_revision",
                                      readonly=False)
    sh_manage_chatter_history=fields.Boolean("Manage Chatter History",
                                             related="company_id.sh_manage_chatter_history",
                                             readonly=False)
