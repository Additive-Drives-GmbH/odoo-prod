# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SyscoonNumbersAutomaticMode(models.Model):
    _name = "syscoon.numbers.automatic.mode"
    _description = "syscoon Numbers Automatic Mode"

    name = fields.Char(translate=True)
    code = fields.Char()
