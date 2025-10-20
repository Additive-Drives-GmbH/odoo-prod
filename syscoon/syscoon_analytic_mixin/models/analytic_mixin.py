# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import models


class AnalyticMixin(models.AbstractModel):
    _inherit = "analytic.mixin"

    def _fetch_analytic_accounts(self):
        """Fetch the analytic accounts for the current recordset."""
        analytic_ids = []
        for rec in self:
            if not rec.analytic_distribution:
                continue
            for analytic_keys in list(rec.analytic_distribution.keys()):
                for analytic_id in analytic_keys.split(","):
                    analytic_ids.append(int(analytic_id))
        return self.env["account.analytic.account"].browse(analytic_ids).exists()
