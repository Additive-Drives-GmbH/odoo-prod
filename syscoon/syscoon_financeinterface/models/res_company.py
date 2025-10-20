# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    export_finance_interface = fields.Selection(
        selection=[("none", "None")], default="none"
    )
    export_finance_interface_active = fields.Boolean()
    financeinterface_template_id = fields.Many2one(
        "syscoon.financeinterface.template",
        "Export Template",
        default=lambda self: self.env.ref(
            "syscoon_financeinterface.syscoon_financeinterface_main_template",
            raise_if_not_found=False,
        ),
    )
    datev_default_journal_ids = fields.Many2many(
        "account.journal",
        string="Default Journals",
        domain="[('company_id', '=', company_id)]",
    )
    export_invoice_reset_active = fields.Boolean(
        string="Reset Invoices to Draft after Export"
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._create_financeinterface_export_sequence()
        companies._set_visible_financeinterface_menu()
        return companies

    def write(self, vals):
        res = super().write(vals)
        if "export_finance_interface_active" in vals:
            self._set_visible_financeinterface_menu()
        return res

    def _update_existing_financeinterface_export_sequence(self):
        open_sequence = self.env["ir.sequence"].search(
            [
                ("code", "=", "syscoon.financeinterface.name"),
                ("company_id", "=", False),
            ],
            limit=1,
        )
        main_company = self.env.ref("base.main_company")
        if not main_company:
            main_company = self[:1]
        if open_sequence:
            open_sequence.write({"company_id": main_company.id})

    def _create_financeinterface_export_sequence(self):
        for rec in self:
            sequence = self.env["ir.sequence"].search(
                [
                    ("code", "=", "syscoon.financeinterface.name"),
                    ("company_id", "=", rec.id),
                ],
                limit=1,
            )
            if not sequence:
                self.env["ir.sequence"].create(
                    {
                        "name": f"Export-ID ({rec.name})",
                        "prefix": "EXTF_",
                        "code": "syscoon.financeinterface.name",
                        "padding": 8,
                        "company_id": rec.id,
                        "number_increment": 1,
                        "number_next": 1,
                    }
                )

    def _set_visible_financeinterface_menu(self):
        finance_menu = self.env.ref(
            "syscoon_financeinterface.menu_finance_interface", raise_if_not_found=False
        )
        if not finance_menu:
            return

        for company in self:
            if company.export_finance_interface_active:
                if finance_menu.id in company.restrict_menu_ids.ids:
                    company.restrict_menu_ids = [Command.unlink(finance_menu.id)]
            else:
                if finance_menu.id not in company.restrict_menu_ids.ids:
                    company.restrict_menu_ids = [Command.link(finance_menu.id)]
