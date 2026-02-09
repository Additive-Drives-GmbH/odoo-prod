from odoo import Command, api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_proforma_textblocks(self):
        """Get proforma text blocks based on shipping or partner country."""
        self.ensure_one()
        partner = self.partner_shipping_id or self.partner_id
        if not partner.country_id:
            return self.env["text.block"]
        return self.env["text.block"].search(
            [
                ("proforma", "=", True),
                ("country_id", "=", partner.country_id.id),
            ]
        )

    @api.onchange("partner_shipping_id", "partner_id")
    def _onchange_partner_proforma_textblocks(self):
        for record in self:
            proforma_textblocks = record._get_proforma_textblocks()
            if proforma_textblocks:
                existing_ids = record._origin.bottom_text_block_ids.ids
                new_textblocks = proforma_textblocks.filtered(
                    lambda tb, existing_ids=existing_ids: tb.id not in existing_ids
                )
                if new_textblocks:
                    record._origin.bottom_text_block_ids = [
                        Command.link(tb.id) for tb in new_textblocks
                    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            proforma_textblocks = record._get_proforma_textblocks()
            if proforma_textblocks:
                record.bottom_text_block_ids = [
                    Command.link(tb.id) for tb in proforma_textblocks
                ]
        return records
