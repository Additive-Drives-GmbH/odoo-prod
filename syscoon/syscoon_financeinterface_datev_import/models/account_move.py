# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    syscoon_datev_import_id = fields.Many2one(
        "syscoon.datev.import", "DATEV Import", readonly=True
    )
    syscoon_datev_import_guid = fields.Char("DATEV Move GUID")

    def _prepare_datev_reconcile_lines(self):
        reconcile_lines = self.env["account.move.line"]
        if not self.ref:
            return reconcile_lines
        for line in self.line_ids:
            if line.account_id.account_type not in [
                "liability_payable",
                "asset_receivable",
            ]:
                continue
            reconcile_lines |= line
        for line in self._get_opposite_datev_moves(ref=self.ref).line_ids:
            if line.id in reconcile_lines.ids or line.account_id.account_type not in [
                "liability_payable",
                "asset_receivable",
            ]:
                continue
            reconcile_lines |= line
        return reconcile_lines

    def _get_opposite_datev_moves(self, ref):
        return self.env["account.move"].search(
            [
                ("datev_ref", "=", ref),
                ("payment_state", "in", ["not_paid", "in_payment", "partial"]),
            ]
        )
