from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    contact_id = fields.Many2one(
        comodel_name="res.partner",
    )
    country_of_origin_id = fields.Many2one(
        comodel_name="res.country",
        domain="[('code', 'in', ['DE','US'])]",
    )

    def _get_position_step(self):
        """
        Return the increment step for positions.
        """
        return 10

    def _recompute_positions(self):  # pylint: disable=W8110
        """
        Recalculate with step of 10
        """
        super()._recompute_positions()
        step = self._get_position_step()
        for sale in self:
            lines = sale.order_line.filtered(lambda line: not line.display_type)
            lines = lines.sorted(key=lambda x: (x.sequence, x.id))
            position = step
            for line in lines:
                line.position = position
                position += step
