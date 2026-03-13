from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    locked_positions = fields.Boolean(compute="_compute_locked_positions")

    @api.depends("state")
    def _compute_locked_positions(self):
        for record in self:
            record.locked_positions = record.state != "draft"

    def button_confirm(self):
        self.recompute_positions()
        return super().button_confirm()

    def action_rfq_send(self):
        self.recompute_positions()
        return super().action_rfq_send()

    def recompute_positions(self):
        for purchase in self:
            if (
                purchase.locked_positions
                or purchase.company_id.disable_purchase_position_recompute
            ):
                continue
            purchase._recompute_positions()

    def _recompute_positions(self):
        lines = self.order_line.filtered(lambda line: not line.display_type)
        lines = lines.sorted(key=lambda x: (x.sequence, x.id))
        for index, line in enumerate(lines):
            line.position = (index + 1) * 10
