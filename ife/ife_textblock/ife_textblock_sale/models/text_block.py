from odoo import api, fields, models


class TextBlock(models.Model):
    _inherit = "text.block"

    @api.model
    def _get_model_names(self):
        res = super()._get_model_names()
        res.extend(["sale.order", "sale.order.line", "sale.order.template"])
        return res

    not_print_custom_view = fields.Boolean(
        string="Not in Customer View",
        help="If checked the textblock will not be print at Customer View.",
    )
    show_in_invoice = fields.Boolean(
        help="If checked the textblock will be shown in invoice.",
    )

    show_in_order = fields.Boolean(
        help="If unchecked, the text block is only shown on quotations.",
    )

    sale_line_id = fields.Many2one("sale.order.line", string="SO Line")

    @api.onchange("show_in_invoice")
    def _show_in_invoice(self):
        for record in self:
            account_move = self.env.ref("account.model_account_move")
            if record.show_in_invoice:
                if account_move not in record.model_ids:
                    record.write({"model_ids": [(4, account_move.id)]})

    @api.onchange("template_id")
    def _onchange_template_id(self):  # pylint: disable=W8110
        super()._onchange_template_id()
        if self.template_id:
            self.show_in_invoice = self.template_id.show_in_invoice
            self.not_print_custom_view = self.template_id.not_print_custom_view

    def _prepare_textblock_values(self, **kwargs):
        res = super()._prepare_textblock_values(**kwargs)

        if "sale_line_id" in kwargs:
            res["sale_line_id"] = kwargs["sale_line_id"]

        res.update(
            {
                "not_print_custom_view": self.not_print_custom_view,
                "show_in_order": self.show_in_order,
                "show_in_invoice": self.show_in_invoice,
            }
        )

        return res
