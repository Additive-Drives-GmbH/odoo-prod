# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    restrict_menu_ids = fields.Many2many(
        comodel_name="ir.ui.menu",
        relation="company_menu_rule_rel",
        column1="company_id",
        column2="menu_id",
        string="Restricted Menus",
        help="Menus that will be hidden for this company",
    )

    def write(self, vals):
        res = super().write(vals)
        if "restrict_menu_ids" in vals:
            self.env.registry.clear_cache()
        return res
