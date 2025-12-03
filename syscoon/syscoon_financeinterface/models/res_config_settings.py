# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SyscoonFinanceinterfaceConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_export_finance_interface = fields.Selection(
        related="company_id.export_finance_interface", readonly=False
    )
    company_export_finance_interface_active = fields.Boolean(
        related="company_id.export_finance_interface_active", readonly=False
    )
    company_financeinterface_template_id = fields.Many2one(
        related="company_id.financeinterface_template_id", readonly=False
    )
    company_datev_default_journal_ids = fields.Many2many(
        related="company_id.datev_default_journal_ids", readonly=False
    )
    company_export_invoice_reset_active = fields.Boolean(
        related="company_id.export_invoice_reset_active", readonly=False
    )
