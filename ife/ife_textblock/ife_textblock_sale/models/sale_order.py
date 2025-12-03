import logging

from odoo import Command, api, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = [
        "sale.order",
        "textblock.item.mixin",
    ]
    _name = "sale.order"

    def _prepare_invoice(self):
        result = super()._prepare_invoice()
        above_text_blocks = self.above_text_block_ids.filtered(
            lambda t: t.show_in_invoice
        )
        bottom_text_blocks = self.bottom_text_block_ids.filtered(
            lambda t: t.show_in_invoice
        )
        res_model_id = self.env["ir.model"]._get("account.move")
        above_text_block_data = []
        bottom_text_block_data = []
        if above_text_blocks:
            above_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        res_model="account.move",
                        res_model_id=res_model_id.id,
                        model_ids=[(6, 0, res_model_id.ids)],
                    )
                )
                for line in above_text_blocks.sorted(lambda o: o.sequence)
            ]
        if bottom_text_blocks:
            bottom_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        res_model="account.move",
                        res_model_id=res_model_id.id,
                        model_ids=[(6, 0, res_model_id.ids)],
                    )
                )
                for line in bottom_text_blocks.sorted(lambda o: o.sequence)
            ]
        result["above_text_block_ids"] = above_text_block_data
        result["bottom_text_block_ids"] = bottom_text_block_data
        return result

    @api.onchange("sale_order_template_id")
    def _onchange_sale_order_template_id(self):  # pylint: disable=W8110
        super()._onchange_sale_order_template_id()
        if self.sale_order_template_id:
            sale_order_template = self.sale_order_template_id.with_context(
                lang=self.partner_id.lang
            )

            above_text_block_data = [Command.clear()]
            bottom_text_block_data = [Command.clear()]
            res_model_id = self.env["ir.model"]._get("sale.order")
            above_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        res_model="sale.order",
                        res_model_id=res_model_id.id,
                        res_id=self.id,
                        model_ids=[(6, 0, res_model_id.ids)],
                    )
                )
                for line in sale_order_template.above_text_block_ids.sorted(
                    lambda o: o.sequence
                )
            ]
            bottom_text_block_data += [
                Command.create(
                    line._prepare_textblock_values(
                        res_model="sale.order",
                        res_model_id=res_model_id.id,
                        object_id=self.id,
                        model_ids=[(6, 0, res_model_id.ids)],
                    )
                )
                for line in sale_order_template.bottom_text_block_ids.sorted(
                    lambda o: o.sequence
                )
            ]
            self._origin.above_text_block_ids = above_text_block_data
            self._origin.bottom_text_block_ids = bottom_text_block_data
        else:
            self._origin.above_text_block_ids = [Command.clear()]
            self._origin.bottom_text_block_ids = [Command.clear()]

    @api.model_create_multi
    def create(self, vals_list):
        record_list = super().create(vals_list)
        for record in record_list:
            above_text_block_data = []
            bottom_text_block_data = []
            sale_order_template = record.sale_order_template_id.with_context(
                lang=record.partner_id.lang
            )
            if (
                not self.env.context.get("is_record_copied")
                and record.sale_order_template_id
            ):
                record.above_text_block_ids = [Command.clear()]
                record.bottom_text_block_ids = [Command.clear()]
                res_model_id = self.env["ir.model"]._get("sale.order")
                above_text_block_data += [
                    Command.create(
                        line._prepare_textblock_values(
                            res_model="sale.order",
                            res_model_id=res_model_id.id,
                            res_id=record.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                        )
                    )
                    for line in sale_order_template.above_text_block_ids.sorted(
                        lambda o: o.sequence
                    )
                ]
                bottom_text_block_data += [
                    Command.create(
                        line._prepare_textblock_values(
                            res_model="sale.order",
                            res_model_id=res_model_id.id,
                            object_id=record.id,
                            model_ids=[(6, 0, res_model_id.ids)],
                        )
                    )
                    for line in sale_order_template.bottom_text_block_ids.sorted(
                        lambda o: o.sequence
                    )
                ]
                record.above_text_block_ids = above_text_block_data
                record.bottom_text_block_ids = bottom_text_block_data
        return record_list
