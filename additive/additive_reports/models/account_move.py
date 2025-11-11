from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    country_of_origin_id = fields.Many2one(
        comodel_name="res.country",
    )
