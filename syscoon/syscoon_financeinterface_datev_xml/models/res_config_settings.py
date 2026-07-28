# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SyscoonFinanceinterfaceConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_export_xml_mode = fields.Selection(
        related="company_id.export_xml_mode", readonly=False
    )
    company_export_xml_group_lines = fields.Boolean(
        related="company_id.export_xml_group_lines", readonly=False
    )
    company_export_xml_analytic_accounts = fields.Boolean(
        related="company_id.export_xml_analytic_accounts", readonly=False
    )
    module_syscoon_financeinterface_datev_xml_decrypt = fields.Boolean(
        string="Decrypt PDF files that are encrypted",
        help="This module allows to decrypt PDF files that are encrypted.",
        related="company_id.module_syscoon_financeinterface_datev_xml_decrypt",
        readonly=False,
    )
