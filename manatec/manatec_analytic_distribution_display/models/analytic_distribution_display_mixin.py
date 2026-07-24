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

            account_ids = [int(k) for k in distribution.keys()]
            accounts_by_id = {a.id: a for a in AnalyticAccount.browse(account_ids).exists()}

            # Grouping by plan
            by_plan = {}  # plan_id -> {"sequence": int, "entries": [(name, pct)]}
            for account_id_str, percentage in distribution.items():
                account = accounts_by_id.get(int(account_id_str))
                if not account:
                    continue  # deleted/orphaned Account -> skip
                plan = account.plan_id
                pct = float_round(percentage, precision_digits=precision)
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
