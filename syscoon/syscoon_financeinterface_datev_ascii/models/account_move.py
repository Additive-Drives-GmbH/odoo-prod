# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import uuid
from functools import lru_cache

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    """Adds the posibility to check the move line if they are compatible for
    the DATEV export"""

    _inherit = "account.move"

    datev_checks_enabled = fields.Boolean(
        string="Perform Datev Checks",
        compute="_compute_datev_checks_enabled",
        readonly=True,
        store=True,
    )
    datev_ref = fields.Char(string="DATEV Ref", readonly=False, store=True, copy=False)
    datev_bedi = fields.Char(string="DATEV BEDI", copy=False)

    @api.depends("company_id")
    def _compute_datev_checks_enabled(self):
        for rec in self:
            rec.datev_checks_enabled = (
                rec.company_id.export_finance_interface_active
                and rec.company_id.datev_checks_enabled
            )

    def make_datev_checks(self):
        """Checks the move and the move lines if the counter account is set and
        if the account_id is an automatic account in DATEV. Checks also if the
        taxes are set correctly and if a VAT-ID is required if it is set in the
        partner."""
        errors = self.line_ids._prepare_datev_errors()
        if errors:
            raise UserError("\n".join(errors))
        return errors

    def _assign_datev_values(self):
        @lru_cache
        def _get_val(key, value):
            if not value:
                return ""
            finance_interface = self.env["syscoon.financeinterface"]
            template = finance_interface._export_template()
            ascii_vals = template._template_vals(line_type="ascii")
            exprission_vals = ascii_vals.get(key, {}).get("expression")
            try:
                return finance_interface._apply_regex_config(exprission_vals, key, value)
            except Exception:
                return value

        for move in self:
            if move.datev_checks_enabled:
                move.make_datev_checks()
            datev_ref = (
                move.ref
                if move.journal_id.type == "purchase"
                and move.ref
                and move.company_id.datev_ref_from_ref
                else move.name
            )
            vals = {"datev_ref": _get_val("Belegfeld 1", datev_ref) or datev_ref}
            if (
                move.move_type
                in [
                    "out_invoice",
                    "out_refund",
                    "in_invoice",
                    "in_refund",
                ]
                and move.company_id.datev_use_bedi
                and not move.datev_bedi
            ):
                vals["datev_bedi"] = str(uuid.uuid4())
            move.write(vals)

    def _post(self, soft=True):
        # OVERRIDE
        posted = super()._post(soft=soft)
        posted.filtered(
            lambda m: m.export_finance_interface_active
        )._assign_datev_values()
        return posted

    def _get_datev_ref(self):
        return self.datev_ref or ""

    def _datev_original_moves(self):
        payments = self.payment_ids
        reconciled = payments.reconciled_bill_ids | payments.reconciled_invoice_ids
        return reconciled or self

    def create_new_bedi_uuid(self):
        for rec in self:
            if (
                rec.move_type
                in [
                    "out_invoice",
                    "out_refund",
                    "out_receipt",
                    "in_invoice",
                    "in_refund",
                    "in_receipt",
                ]
                and rec.company_id.datev_use_bedi
            ):
                rec.write({"datev_bedi": str(uuid.uuid4())})

    # ------------------------------------------
    # DATEV Export
    # ------------------------------------------
    def generate_export_lines(self, data):
        """Checks if lines are exportable and inits the generation of the export line"""
        for line in self.line_ids:
            if line._is_datev_invalid_line():
                continue
            datev_move = self._datev_move(line)
            line_data = {
                "move": self,
                "datev_move": datev_move,
                "export": data["interface"].export_template(),
            }
            data["lines"].setdefault(line.id, line_data)
            line.generate_export_line(data)
        self.group_converted_move_lines(data)

    def group_converted_move_lines(self, data):
        lines = [
            data["lines"][ml]["export"]
            for ml in data["lines"]
            if data["lines"][ml]["move"].id == self.id
        ]
        if not self.journal_id.datev_ascii_group_moves:
            data["grouped_lines"] += [
                data["interface"]._apply_template_config(self, line, data)
                for line in lines
            ]
            return
        grouped_vals = {}
        sum_keys = ["Basis-Umsatz", "Umsatz (ohne Soll/Haben-Kz)"]
        for vals in lines:
            key = self._generate_group_key(vals)
            grouped_vals.setdefault(
                key, {**vals, **{sum_key: 0.0 for sum_key in sum_keys}}
            )
            for sum_key in sum_keys:
                grouped_vals[key][sum_key] += vals[sum_key] if vals[sum_key] else 0.0
        new_lines = []
        for line in grouped_vals.values():
            new_lines.append(data["interface"]._apply_template_config(self, line, data))
        data["grouped_lines"] += new_lines

    def _generate_group_key(self, line_values):
        return "-".join([str(line_values[key]) for key in self._group_match_fields()])

    def _group_match_fields(self):
        return [
            "Konto",
            "WKZ Umsatz",
            "BU-Schlüssel",
            "KOST1 - Kostenstelle",
            "KOST2 - Kostenstelle",
            "Soll/Haben-Kennzeichen",
            "Gegenkonto (ohne BU-Schlüssel)",
        ]

    def _datev_move(self, line):
        move_types = self.get_sale_types() + self.get_purchase_types()
        is_asset = "asset_id" in self._fields
        aml_obj = self.env["account.move.line"]
        move = self
        if reconciled_line := aml_obj.search(
            [
                ("id", "in", line._reconciled_lines()),
                ("move_id", "!=", self.id),
                ("move_id.move_type", "in", move_types),
            ],
            limit=1,
        ):
            move = reconciled_line.move_id
        elif is_asset and self.asset_id.original_move_line_ids:
            move = self.asset_id.original_move_line_ids.move_id[:1]
        move = move._datev_original_moves()[:1]
        return move
