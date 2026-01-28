from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    disable_purchase_position_recompute = fields.Boolean(
        related="company_id.disable_purchase_position_recompute",
        readonly=False,
    )
