# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import api, SUPERUSER_ID

from . import models


def _init_ascii_export_accounts(env):
    # No need to get the field reference since we're writing directly to the model
    for company in env["res.company"].search([]):
        partners = env["res.partner"].search([])
        for partner in partners:
            # Set the value directly using the selection field's string value
            partner.with_company(company).write({"datev_exported": False})
