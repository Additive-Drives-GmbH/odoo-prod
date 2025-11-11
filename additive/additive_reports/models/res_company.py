from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    general_manager_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="res_company_general_manager_rel",
        column1="company_id",
        column2="manager_id",
        help="General managers to be displayed in reports.",
    )
