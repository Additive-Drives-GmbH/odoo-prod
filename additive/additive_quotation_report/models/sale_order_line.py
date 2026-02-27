from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    report_description = fields.Text(
        help="Description to be included in the sale report",
    )

    @api.onchange("product_id")
    def _onchange_product_id_set_report_description(self):
        for line in self:
            lang = line.order_id._get_lang()
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if line.product_id:
                line.report_description = (
                    line.product_id.description_sale or line.product_id.display_name
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            lang = line.order_id._get_lang()
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if line.product_id:
                line.report_description = (
                    line.product_id.description_sale or line.product_id.display_name
                )
        return lines

    @api.model
    def _format_position(self, position):
        """
        Override to use 4 digits instead of 3
        """
        if not position:
            return ""
        return str(position).zfill(4)

    def _get_position_step(self):
        """
        Return the increment step for positions."""
        return 10

    def _add_next_position_on_new_line(self, vals_list):
        """
        Override to use step of 10
        """
        step = self._get_position_step()
        sale_ids = [
            line["order_id"]
            for line in vals_list
            if not line.get("display_type") and line.get("order_id")
        ]
        if sale_ids:
            ids = tuple(set(sale_ids))
            self.flush_model()
            query = """
            SELECT order_id, coalesce(max(position), 0) FROM sale_order_line
            WHERE order_id in %s GROUP BY order_id;
            """
            self.env.cr.execute(query, (ids,))
            default_pos = {key: 1 for key in ids}
            existing_pos = {
                order_id: pos + 1 for order_id, pos in self.env.cr.fetchall()
            }
            sale_pos = {**default_pos, **existing_pos}
            for line in vals_list:
                if not line.get("display_type"):
                    line["position"] = sale_pos[line["order_id"]]
                    # start update
                    sale_pos[line["order_id"]] += step
                    # end update
        return vals_list

    def _prepare_invoice_line(self, **optional_values):
        self.ensure_one()
        invoice_line_values = super()._prepare_invoice_line(**optional_values)
        invoice_line_values["report_description"] = self.report_description
        return invoice_line_values

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        if self.report_description:
            values["description_picking"] = self.report_description
        return values
