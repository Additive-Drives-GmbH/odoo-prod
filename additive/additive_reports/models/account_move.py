from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_origin_countries(self):
        self.ensure_one()
        # Collect unique countries of origin from all products in the invoice lines
        countries = self.invoice_line_ids.mapped("product_id.product_tmpl_id.country_of_origin")

        # Filter out the country that matches the shipping address country
        shipping_country = self.partner_shipping_id.country_id
        if shipping_country:
            countries = countries.filtered(lambda c: c != shipping_country)

        # Return a comma-separated string of country names, sorted alphabetically
        return ", ".join(countries.sorted("name").mapped("name"))
