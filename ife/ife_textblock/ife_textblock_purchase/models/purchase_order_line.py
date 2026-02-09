from odoo import Command, api, models


class PurchaseOrderLine(models.Model):
    _inherit = [
        "purchase.order.line",
        "textblock.item.mixin",
    ]
    _name = "purchase.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        record_list = super().create(vals_list)
        for record in record_list:
            # fill textblock from product
            record.text_block_id = []
            if not self.env.context.get("is_record_copied"):
                record.update_inline_textblock(product=record.product_id)
                record.update_preline_textblock(product=record.product_id, sequence=99)
                record.update_postline_textblock(product=record.product_id, sequence=99)
        return record_list

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if "product_id" in vals:
                record.text_block_id = []
                product = self.env["product.product"].browse(vals.get("product_id"))
                # fill textblock from product
                record.update_inline_textblock(product=product)
                record.update_preline_textblock(product=product, sequence=99)
                record.update_postline_textblock(product=product, sequence=99)
        return res

    def update_inline_textblock(self, product):
        if product:
            if product.bottom_text_block_ids:
                res_model_id = self.env["ir.model"]._get("purchase.order.line")
                for block in product.bottom_text_block_ids.filtered(
                    lambda t: t.inline_check
                ):
                    self.text_block_id = self.env["text.block"].create(
                        block._prepare_textblock_values(
                            inline_check=True,
                            res_id=self.id,
                            res_model="purchase.order.line",
                            res_model_id=res_model_id.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                        )
                    )
            # check product template
            else:
                if (
                    product.product_tmpl_id
                    and product.product_tmpl_id.above_text_block_ids
                ):
                    res_model_id = self.env["ir.model"]._get("purchase.order.line")
                    for block in product.product_tmpl_id.above_text_block_ids.filtered(
                        lambda t: t.inline_check
                    ):
                        self.text_block_id = self.env["text.block"].create(
                            block._prepare_textblock_values(
                                inline_check=True,
                                res_id=self.id,
                                res_model="purchase.order.line",
                                res_model_id=res_model_id.id,
                                model_ids=[(6, 0, res_model_id.ids)],
                            )
                        )

    def update_preline_textblock(self, product, sequence):
        existing_above_text_block = self.order_id.above_text_block_ids.filtered(
            lambda t: t.purchase_line_id.id == self.id
        )
        self.order_id.above_text_block_ids = [
            Command.unlink(existing_above_text_block.ids)
        ]
        res_model_id = self.env["ir.model"]._get("purchase.order")
        above_text_block_data = []
        if product:
            if product.bottom_text_block_ids.filtered(lambda t: t.preline_check):
                above_text_block_data += [
                    Command.create(
                        line._prepare_textblock_values(
                            sequence=sequence,
                            res_id=self.order_id.id,
                            res_model_id=res_model_id.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                            purchase_line_id=self.id,
                        )
                    )
                    for line in product.bottom_text_block_ids.filtered(
                        lambda t: t.preline_check
                    ).sorted(lambda o: o.sequence)
                ]
                self.order_id.above_text_block_ids = above_text_block_data
            # check product template
            else:
                if (
                    product.product_tmpl_id
                    and product.product_tmpl_id.above_text_block_ids.filtered(
                        lambda t: t.preline_check
                    )
                ):
                    above_text_block_data += [
                        Command.create(
                            line._prepare_textblock_values(
                                sequence=sequence,
                                res_id=self.order_id.id,
                                res_model_id=res_model_id.id,
                                model_ids=[(6, 0, res_model_id.ids)],
                                purchase_line_id=self.id,
                            )
                        )
                        for line in (
                            product.product_tmpl_id.above_text_block_ids.filtered(
                                lambda t: t.preline_check
                            ).sorted(lambda o: o.sequence)
                        )
                    ]
                    self.order_id.above_text_block_ids = above_text_block_data

    def update_postline_textblock(self, product, sequence):
        existing_bottom_text_block = self.order_id.bottom_text_block_ids.filtered(
            lambda t: t.purchase_line_id.id == self.id
        )
        res_model_id = self.env["ir.model"]._get("purchase.order")
        self.order_id.bottom_text_block_ids = [
            Command.unlink(existing_bottom_text_block.ids)
        ]
        bottom_text_block_data = []
        if product:
            if product.bottom_text_block_ids.filtered(lambda t: t.postline_check):
                bottom_text_block_data += [
                    Command.create(
                        line._prepare_textblock_values(
                            sequence=sequence,
                            object_id=self.order_id.id,
                            res_model_id=res_model_id.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                            purchase_line_id=self.id,
                        )
                    )
                    for line in product.bottom_text_block_ids.filtered(
                        lambda t: t.postline_check
                    ).sorted(lambda o: o.sequence)
                ]
                self.order_id.bottom_text_block_ids = bottom_text_block_data
            # check product template
            else:
                if (
                    product.product_tmpl_id
                    and product.product_tmpl_id.above_text_block_ids.filtered(
                        lambda t: t.postline_check
                    )
                ):
                    bottom_text_block_data += [
                        Command.create(
                            line._prepare_textblock_values(
                                sequence=sequence,
                                object_id=self.order_id.id,
                                res_model_id=res_model_id.id,
                                model_ids=[(6, 0, res_model_id.ids)],
                                purchase_line_id=self.id,
                            )
                        )
                        for line in (
                            product.product_tmpl_id.above_text_block_ids.filtered(
                                lambda t: t.postline_check
                            ).sorted(lambda o: o.sequence)
                        )
                    ]
                    self.order_id.bottom_text_block_ids = bottom_text_block_data
