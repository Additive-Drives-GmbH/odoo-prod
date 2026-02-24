from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    our_nr_by_customer = fields.Char(
        string="Our Number by Customer",
    )
