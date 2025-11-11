from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    foreign_account = fields.Boolean(
        help="Check this box if the bank account is used for foreign transactions.",
    )
