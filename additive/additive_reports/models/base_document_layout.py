from odoo import fields, models


class BaseDocumentLayout(models.TransientModel):
    _inherit = "base.document.layout"

    general_manager_ids = fields.Many2many(
        related="company_id.general_manager_ids",
        readonly=True,
    )
