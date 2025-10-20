# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    datev_payment_conditons_id = fields.Integer("DATEV Payment Term ID")
    export_finance_interface_active = fields.Boolean(
        compute="_compute_export_finance_interface_active"
    )

    @api.constrains("datev_payment_conditons_id")
    def _check_value(self):
        if self.datev_payment_conditons_id > 99 or self.datev_payment_conditons_id < 0:
            raise ValidationError(_("Only a value between 0 and 99 is allowed."))

    def _compute_export_finance_interface_active(self):
        for record in self:
            if record.company_id.export_finance_interface_active:
                record.export_finance_interface_active = (
                    record.company_id.export_finance_interface_active
                )
            else:
                record.export_finance_interface_active = (
                    self.env.company.export_finance_interface_active
                )
