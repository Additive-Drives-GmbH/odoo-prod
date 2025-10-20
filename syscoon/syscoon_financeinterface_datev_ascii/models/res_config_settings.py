# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SyscoonFinanceinterfaceConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_export_finance_interface = fields.Selection(
        related="company_id.export_finance_interface", readonly=False
    )
    company_datev_export_method = fields.Selection(
        related="company_id.datev_export_method", readonly=False
    )
    company_datev_checks_enabled = fields.Boolean(
        related="company_id.datev_checks_enabled", readonly=False
    )
    company_datev_enable_fixing = fields.Boolean(
        related="company_id.datev_enable_fixing", readonly=False
    )
    company_datev_accountant_number = fields.Char(
        related="company_id.datev_accountant_number", readonly=False
    )
    company_datev_client_number = fields.Char(
        related="company_id.datev_client_number", readonly=False
    )
    company_datev_voucher_date_format = fields.Selection(
        related="company_id.datev_voucher_date_format", readonly=False, required=True
    )
    company_datev_account_code_digits = fields.Integer(
        related="company_id.datev_account_code_digits", readonly=False
    )
    company_datev_remove_leading_zeros = fields.Boolean(
        related="company_id.datev_remove_leading_zeros", readonly=False
    )
    company_datev_auto_set_accounts = fields.Selection(
        related="company_id.datev_auto_set_accounts", readonly=False
    )
    company_datev_use_bedi = fields.Boolean(
        related="company_id.datev_use_bedi", readonly=False
    )
    company_datev_ref_from_ref = fields.Boolean(
        related="company_id.datev_ref_from_ref",
        readonly=False,
        string="Use Vendor Reference",
    )
