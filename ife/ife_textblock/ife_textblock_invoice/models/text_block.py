from odoo import api, fields, models


class TextBlock(models.Model):
    _inherit = "text.block"

    @api.model
    def _get_model_names(self):
        res = super()._get_model_names()
        res.extend(["account.move", "account.move.line"])
        return res

    move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Move Line",
    )

    def _prepare_textblock_values(self, **kwargs):
        res = super()._prepare_textblock_values(**kwargs)
        if "move_line_id" in kwargs:
            res["move_line_id"] = kwargs["move_line_id"]
        return res
