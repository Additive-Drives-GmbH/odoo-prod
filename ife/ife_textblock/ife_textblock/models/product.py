from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = [
        "product.template",
        "textblock.item.mixin",
    ]
    _name = "product.template"

    @api.constrains("above_text_block_ids")
    def _constrains_above_text_block_ids(self):
        for record in self:
            if record.above_text_block_ids:
                if (
                    len(
                        record.above_text_block_ids.filtered(
                            lambda block: block.inline_check
                        )
                    )
                    > 1
                ):
                    raise ValidationError(
                        _("We can not have more than one in-line text block.")
                    )


class ProductProduct(models.Model):
    _inherit = [
        "product.product",
        "textblock.item.mixin",
    ]
    _name = "product.product"

    @api.constrains("bottom_text_block_ids")
    def _constrains_bottom_text_block_ids(self):
        for record in self:
            if record.bottom_text_block_ids:
                if (
                    len(
                        record.bottom_text_block_ids.filtered(
                            lambda block: block.inline_check
                        )
                    )
                    > 1
                ):
                    raise ValidationError(
                        _("We can not have more than one in-line text block.")
                    )
