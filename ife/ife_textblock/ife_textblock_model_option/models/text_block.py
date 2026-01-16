from odoo import fields, models


class TextBlock(models.Model):
    _inherit = "text.block"

    textblock_position = fields.Selection(
        selection=[("pre", "Pre Order Lines"), ("post", "Post Order Lines")],
        default="pre",
        help="Specify whether to show the textblock "
        "before (Pre) or after (Post) the main content.",
    )

    direct_render = fields.Boolean(
        default=False,
        help="If checked, the textblock will be rendered directly in the report.",
    )
