from odoo import fields, models


class TextBlockItemMixin(models.AbstractModel):
    _name = "textblock.item.mixin"
    _description = (
        "Mixin model for applying to any object that wants to handle Textblock Items"
    )

    above_text_block_ids = fields.One2many(
        comodel_name="text.block",
        inverse_name="res_id",
        string="Pre-Lines Textblocks",
        copy=True,
    )
    bottom_text_block_ids = fields.One2many(
        comodel_name="text.block",
        inverse_name="object_id",
        string="Post-Lines Textblocks",
        copy=True,
    )

    text_block_id = fields.Many2one(
        comodel_name="text.block", string="In-Line Textblock"
    )

    def unlink(self):
        """Override unlink to delete Textblock. When deleting the record."""
        if not self:
            return True
        # Delete preline text blocks related to the record
        self.env["text.block"].sudo().search(
            [("res_model", "=", self._name), ("res_id", "in", self.ids)]
        ).unlink()
        # Delete postline text blocks related to the record
        self.env["text.block"].sudo().search(
            [("res_model", "=", self._name), ("object_id", "in", self.ids)]
        ).unlink()
        res = super().unlink()
        return res

    def copy(self, default=None):
        if (
            self.above_text_block_ids
            or self.bottom_text_block_ids
            or self.text_block_id
        ):
            self = self.with_context(is_record_copied=True)
        return super().copy(default=default)
