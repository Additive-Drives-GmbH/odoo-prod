from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    report_description = fields.Text(
        help="Description to be included in the sale report",
    )

    @api.onchange("product_id")
    def _onchange_product_id_set_report_description(self):
        for line in self:
            lang = line.move_id.partner_id.lang
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if (
                line.product_id
                and line.move_id.move_type in ["out_invoice", "out_refund"]
                and not line.report_description
            ):
                line.report_description = (
                    line.product_id.description_sale or line.product_id.display_name
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            lang = line.move_id.partner_id.lang
            if lang != self.env.lang:
                line = line.with_context(lang=lang)
            if (
                line.product_id
                and line.move_id.move_type in ["out_invoice", "out_refund"]
                and not line.report_description
            ):
                line.report_description = (
                    line.product_id.description_sale or line.product_id.display_name
                )
        return lines
