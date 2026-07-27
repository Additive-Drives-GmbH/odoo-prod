# -*- coding: utf-8 -*-
"""
    Author: Denis Orechov (denis.orechov@manatec.de)
    Copyright: 2026, manaTec GmbH
    Date created: 27.07.2026
"""

from odoo import api, fields, models
from odoo.tools import float_round


class AnalyticDistributionDisplayMixin(models.AbstractModel):
    _name = "analytic.distribution.display.mixin"
    _description = "Analytic Distribution Display Mixin"

    analytic_account_display = fields.Char(
        string="Analytic Account Display",
        compute="_compute_analytic_account_display",
        store=True,
        compute_sudo=True,
    )

    @api.depends("analytic_distribution")
    def _compute_analytic_account_display(self):
        precision = self.env["decimal.precision"].precision_get("Analytic Percentage")
        AnalyticAccount = self.env["account.analytic.account"].sudo().with_context(active_test=False)

        for line in self:
            distribution = line.analytic_distribution or {}
            if not distribution:
                line.analytic_account_display = ""
                continue

            account_ids = [
                int(_id)
                for k in distribution.keys()
                for _id in str(k).split(",")
                if _id.strip().isdigit()
            ]
            accounts_by_id = {a.id: a for a in AnalyticAccount.browse(account_ids).exists()}

            # Grouping by plan
            by_plan = {}  # plan_id -> {"sequence": int, "entries": [(name, pct)]}
            for k, percentage in distribution.items():
                pct = float_round(percentage, precision_digits=precision)
                for _id in str(k).split(","):
                    if not _id.strip().isdigit():
                        continue
                    account = accounts_by_id.get(int(_id.strip()))
                    if not account:
                        continue  # deleted/orphaned Account -> skip
                    plan = account.plan_id
                    by_plan.setdefault(plan.id, {"sequence": plan.sequence or 0, "entries": []})
                    by_plan[plan.id]["entries"].append((account.name, pct))

            # Sorting: primarily by plan sequence, secondary by percantage descending
            parts = []
            for plan_id in sorted(by_plan, key=lambda pid: by_plan[pid]["sequence"]):
                entries = sorted(by_plan[plan_id]["entries"], key=lambda e: -e[1])
                single = len(entries) == 1
                for name, pct in entries:
                    if single:
                        parts.append(name)
                    else:
                        pct_str = f"{pct:.{precision}f}".rstrip("0").rstrip(".") if precision else f"{pct:.0f}"
                        parts.append(f"{name} ({pct_str}%)")

            line.analytic_account_display = " | ".join(parts)
