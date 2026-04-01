from odoo import api, fields, models


class TextBlock(models.Model):
    _inherit = "text.block"

    proforma = fields.Boolean(
        string="For Pro-forma Invoice",
        help="If enabled, this text block will be shown in the proforma invoice report",
    )

    country_id = fields.Many2one(
        comodel_name="res.country",
        help="If set, this text block will only be shown "
        "for customers from this country",
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):  # pylint: disable=W8110
        super()._onchange_template_id()
        if self.template_id:
            self.proforma = self.template_id.proforma
            self.country_id = self.template_id.country_id
