from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_origin_countries(self):
        self.ensure_one()
        countries = self.move_ids.product_id.product_tmpl_id.mapped("country_of_origin")
        contact_country = self.partner_id.country_id
        if contact_country:
            countries = countries.filtered(lambda c: c != contact_country)
        return ", ".join(countries.sorted("name").mapped("name"))
