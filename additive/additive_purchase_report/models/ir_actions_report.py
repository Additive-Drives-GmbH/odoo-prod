from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self.purchase_recompute_positions(report_ref, res_ids)
        return super()._render_qweb_pdf(report_ref, res_ids, data)

    def purchase_recompute_positions(self, report_ref, res_ids):
        report_sudo = self._get_report(report_ref)
        if report_sudo.model == "purchase.order":
            purchases = self.env["purchase.order"].browse(res_ids)
            purchases.recompute_positions()
