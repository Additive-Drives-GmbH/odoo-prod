from odoo import api, fields, models


class TextBlock(models.Model):
    _inherit = "text.block"

    @api.model
    def _get_model_names(self):
        res = super()._get_model_names()
        res.extend(["purchase.order", "purchase.order.line"])
        return res

    purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        readonly=True,
    )

    def _prepare_textblock_values(self, **kwargs):
        res = super()._prepare_textblock_values(**kwargs)
        if "purchase_line_id" in kwargs:
            res["purchase_line_id"] = kwargs["purchase_line_id"]
        return res
