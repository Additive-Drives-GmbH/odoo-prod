from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_countries_of_origin(self):
        """Get unique countries of origin from all products in the picking."""
        self.ensure_one()
        countries = self.env["res.country"]
        for move in self.move_ids:
            if move.product_id.product_tmpl_id.country_of_origin:
                countries |= move.product_id.product_tmpl_id.country_of_origin
        return countries
