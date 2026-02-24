from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    position = fields.Integer(readonly=True, index=True, default=False)
    position_formatted = fields.Char(compute="_compute_position_formatted")
    report_description = fields.Text(
        help="Description to be included in the sale report",
    )

    @api.depends("position")
    def _compute_position_formatted(self):
        for record in self:
            record.position_formatted = record._format_position(record.position)

    @api.onchange("product_id")
    def _onchange_product_id_set_report_description(self):
        for line in self:
            lang = line.order_id.partner_id.lang
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if line.product_id:
                line.report_description = (
                    line.product_id.description_purchase or line.product_id.display_name
                )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._add_next_position_on_new_line(vals_list)
        records = super().create(vals_list)
        for line in records:
            lang = line.order_id.partner_id.lang
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if line.product_id:
                line.report_description = (
                    line.product_id.description_purchase or line.product_id.display_name
                )
        return records

    def unlink(self):
        purchases = self.mapped("order_id")
        res = super().unlink()
        for purchase in purchases:
            purchase.recompute_positions()
        return res

    def _add_next_position_on_new_line(self, vals_list):
        purchase_ids = [
            line["order_id"]
            for line in vals_list
            if not line.get("display_type") and line.get("order_id")
        ]
        if purchase_ids:
            ids = tuple(set(purchase_ids))
            self.flush_model()
            query = """
            SELECT order_id, coalesce(max(position), 0) FROM purchase_order_line
            WHERE order_id in %s GROUP BY order_id;
            """
            self.env.cr.execute(query, (ids,))
            default_pos = {key: 10 for key in ids}
            existing_pos = {
                order_id: pos + 10 for order_id, pos in self.env.cr.fetchall()
            }
            purchase_pos = {**default_pos, **existing_pos}
            for line in vals_list:
                if not line.get("display_type"):
                    line["position"] = purchase_pos[line["order_id"]]
                    purchase_pos[line["order_id"]] += 10
        return vals_list

    @api.model
    def _format_position(self, position):
        if not position:
            return ""
        return str(position).zfill(4)
