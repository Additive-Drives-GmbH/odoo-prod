from odoo import api, models


class TextBlock(models.Model):
    _inherit = "text.block"

    @api.model
    def _get_model_names(self):
        res = super()._get_model_names()
        res.extend(["repair.order"])
        return res
