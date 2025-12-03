from odoo import _, api, fields, models
from odoo.tools.translate import html_translate


class TextBlock(models.Model):
    _name = "text.block"
    _order = "sequence"
    _description = "Text block that can added to reports in related models"
    _rec_name = "textblock"

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if "res_model_id" in fields and res.get("res_model"):
            res_model_id = self.env["ir.model"]._get(res["res_model"])
            res["res_model_id"] = res_model_id.id
            res["model_ids"] = [(6, 0, res_model_id.ids)]
        return res

    @api.model
    def _get_model_names(self):
        res = []
        res.extend(["product.product", "product.template"])
        return res

    textblock = fields.Char()
    model_ids = fields.Many2many(
        comodel_name="ir.model",
        string="Models",
        ondelete="cascade",
        required=True,
        domain=lambda self: [("model", "in", self._get_model_names())],
    )
    text = fields.Html(translate=html_translate)
    post_page_break = fields.Boolean(string="Page Break Before")
    pre_page_break = fields.Boolean(string="Page Break After")
    sequence = fields.Integer(
        help="Gives the sequence order when displaying a list of textblock."
    )
    not_print = fields.Boolean(
        string="Not on Reports",
        help="If checked the textblock will not be print at documents.",
    )

    company_ids = fields.Many2many(
        comodel_name="res.company",
        string="Companies",
        help="""If no company is selected,
            the text block will be available for all companies.""",
    )

    is_template = fields.Boolean(help="Used to separate template textblocks from items")

    res_model_id = fields.Many2one(
        comodel_name="ir.model",
        string="Document Model",
        index=True,
        ondelete="cascade",
        required=True,
    )
    res_model = fields.Char(
        comodel_name="Related Document Model",
        index=True,
        related="res_model_id.model",
        precompute=True,
        store=True,
        readonly=True,
    )
    res_id = fields.Many2oneReference(
        string="Related Document ID", index=True, model_field="res_model"
    )

    object_id = fields.Many2oneReference(
        string="Post Document ID", index=True, model_field="res_model"
    )

    preline_check = fields.Boolean("Pre-line")
    inline_check = fields.Boolean("In-line")
    postline_check = fields.Boolean("Post-line")

    template_id = fields.Many2one(
        comodel_name="text.block",
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self.textblock = self.template_id.textblock
            self.text = self.template_id.text
            self.post_page_break = self.template_id.post_page_break
            self.pre_page_break = self.template_id.pre_page_break
            self.not_print = self.template_id.not_print
            self.preline_check = self.template_id.preline_check
            self.inline_check = self.template_id.inline_check
            self.postline_check = self.template_id.postline_check
        else:
            self.textblock = _("Manual text block")

    def _prepare_textblock_values(self, **kwargs):
        """Give the values to create the corresponding text block.

        :return: `text.block.item` create values
        :rtype: dict"""
        self.ensure_one()
        return {
            "textblock": self.textblock,
            "template_id": self.template_id.id,
            "text": self.text,
            "sequence": kwargs.get("sequence", self.sequence),
            "not_print": self.not_print,
            "post_page_break": self.post_page_break,
            "pre_page_break": self.pre_page_break,
            "not_print_custom_view": self.not_print_custom_view,
            "show_in_invoice": self.show_in_invoice,
            "inline_check": kwargs.get("inline_check"),
            "res_model": kwargs.get("res_model"),
            "res_model_id": kwargs.get("res_model_id"),
            "res_id": kwargs.get("res_id"),
            "model_ids": kwargs.get("model_ids"),
        }
