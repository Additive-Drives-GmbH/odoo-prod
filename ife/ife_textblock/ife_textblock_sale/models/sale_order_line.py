from odoo import Command, api, models


class SaleOrderLine(models.Model):
    _inherit = [
        "sale.order.line",
        "textblock.item.mixin",
    ]
    _name = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        record_list = super().create(vals_list)
        for record in record_list:
            # fill textblock from product
            if not self.env.context.get("is_record_copied"):
                record.update_inline_textblock(product=record.product_id)
                record.update_preline_textblock(product=record.product_id, sequence=99)
                record.update_postline_textblock(product=record.product_id, sequence=99)
        return record_list

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if "product_id" in vals:
                # fill textblock from product
                record.text_block_id = []
                product = self.env["product.product"].browse(vals.get("product_id"))
                record.update_inline_textblock(product=product)
                record.update_preline_textblock(product=product, sequence=99)
                record.update_postline_textblock(product=product, sequence=99)
        return res

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res_model_id = self.env["ir.model"]._get("account.move.line")
        text_block = self.text_block_id.filtered(lambda t: t.show_in_invoice)
        if text_block:
            res["text_block_id"] = (
                self.env["text.block"]
                .create(
                    text_block._prepare_textblock_values(
                        res_model_id=res_model_id.id,
                        res_model="account.move.line",
                        model_ids=[(6, 0, res_model_id.ids)],
                    )
                )
                .id
            )
        return res

    def update_inline_textblock(self, product):
        if product and product.bottom_text_block_ids:
            res_model_id = self.env["ir.model"]._get("sale.order.line")
            for block in product.bottom_text_block_ids:
                if block.inline_check:
                    self.text_block_id = self.env["text.block"].create(
                        block._prepare_textblock_values(
                            inline_check=True,
                            res_id=self.id,
                            res_model="sale.order.line",
                            res_model_id=res_model_id.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                        )
                    )

    def update_preline_textblock(self, product, sequence):
        existing_above_text_block = self.order_id.above_text_block_ids.filtered(
            lambda t: t.sale_line_id.id == self.id
        )
        res_model_id = self.env["ir.model"]._get("sale.order")
        self.order_id.above_text_block_ids = [
            Command.unlink(existing_above_text_block.ids)
        ]
        above_text_block_data = []
        if product and product.bottom_text_block_ids.filtered(
            lambda t: t.preline_check
        ):
            above_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        sequence=sequence,
                        res_id=self.order_id.id,
                        res_model_id=res_model_id.id,
                        res_model="sale.order",
                        model_ids=[(6, 0, res_model_id.ids)],
                        sale_line_id=self.id,
                    )
                )
                for line in product.bottom_text_block_ids.filtered(
                    lambda t: t.preline_check
                ).sorted(lambda o: o.sequence)
            ]
            self.order_id.above_text_block_ids = above_text_block_data

    def update_postline_textblock(self, product, sequence):
        existing_bottom_text_block = self.order_id.bottom_text_block_ids.filtered(
            lambda t: t.sale_line_id.id == self.id
        )
        res_model_id = self.env["ir.model"]._get("sale.order")
        self.order_id.bottom_text_block_ids = [
            Command.unlink(existing_bottom_text_block.ids)
        ]
        bottom_text_block_data = []
        if product and product.bottom_text_block_ids.filtered(
            lambda t: t.postline_check
        ):
            bottom_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        sequence=sequence,
                        object_id=self.order_id.id,
                        res_model_id=res_model_id.id,
                        res_model="sale.order",
                        model_ids=[(6, 0, res_model_id.ids)],
                        sale_line_id=self.id,
                    )
                )
                for line in product.bottom_text_block_ids.filtered(
                    lambda t: t.postline_check
                ).sorted(lambda o: o.sequence)
            ]
            self.order_id.bottom_text_block_ids = bottom_text_block_data
