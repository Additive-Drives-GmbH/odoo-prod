# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    datev_exported = fields.Boolean("Exported", default=False)
    datev_diverse_account = fields.Boolean("Diverse Account")
