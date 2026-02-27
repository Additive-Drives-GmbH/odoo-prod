from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_stock_move_values(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        res = super()._get_stock_move_values(
            product_id,
            product_qty,
            product_uom,
            location_id,
            name,
            origin,
            company_id,
            values,
        )
        sale_line = self.env["sale.order.line"].browse(values.get("sale_line_id"))
        if sale_line and sale_line.report_description:
            res["description_picking"] = sale_line.report_description
        return res

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        res = super()._push_prepare_move_copy_values(move_to_copy, new_date)
        if move_to_copy.description_picking:
            res["description_picking"] = move_to_copy.description_picking
        return res
