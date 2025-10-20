# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    restrict_menu_ids = fields.Many2many(
        related="company_id.restrict_menu_ids",
        readonly=False,
        string="Restricted Menus",
        help="Menus that will be hidden for this company",
    )
