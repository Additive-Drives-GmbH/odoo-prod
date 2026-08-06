# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, _


class SaleOrder(models.Model):
    """Inherit Sale Order to add revision fields."""
    _inherit = "sale.order"

    sh_so_number = fields.Integer('SO Number', copy=False, default=1)
    sh_sale_order_id = fields.Many2one(
        'sale.order', 'SaleOrder', copy=False)
    sh_revision_so_id = fields.Many2many("sale.order",
                                         relation="sale_order_revision_order_rel",
                                         column1="so_id",
                                         column2="revision_id",
                                         string="")

    so_count = fields.Integer(
        'Quality Checks', compute='_compute_get_qc_count')
    sh_sale_revision_config = fields.Boolean(
        "Enable Sale Revisions", related="company_id.sh_sale_revision")

    parent_view_btn = fields.Boolean(
        "Parent Btn", compute="_compute_parent_view_btn")

    def open_quality_check(self):
        """This method is used to open the quality check."""
        po = self.env['sale.order'].search(
            [('sh_sale_order_id', '=', self.id)])
        action = self.env.ref(
            'sh_sale_revisions.sh_action_sale_order_quotation_revision').read()[0]
        action['context'] = {
            'domain': [('id', 'in', po.ids)]
        }
        action['domain'] = [('id', 'in', po.ids)]
        return action

    def for_normal_purchase(self):
        """This method is used for normal purchase."""
        action = {
            "type": "ir.actions.act_window",
            "name": "Sale Order",
            "view_mode": "form",
            "res_model": "sale.order",
            'res_id': self.sh_sale_order_id.id,
            'target': 'current'
        }
        return action

    def _compute_get_qc_count(self):
        """This method is used to count the quality check."""
        if self:
            for rec in self:
                rec.so_count = 0
                qc = self.env['sale.order'].search(
                    [('sh_sale_order_id', '=', rec.id)])
                rec.so_count = len(qc.ids)

    def sh_quotation_revision(self, default=None):
        """This method is used to create the quotation revision."""
        if self:
            self.ensure_one()
            if default is None:
                default = {}
            if 'name' not in default:
                if self.env.company.sh_manage_chatter_history:
                    message_vals = {
                        'message_type': 'comment',
                        'model': 'sale.order',
                        'res_id': self.id,
                        'body': 'Revision Order Number :' + _('%(name)s/%(number)s', name=self.name, number=self.sh_so_number)+"<br />"+'Create Date :'+' '+str(fields.Datetime.now())+'<br />'+'User :'+' '+str(self.env.user.name)
                    }
                    self.env['mail.message'].create(message_vals)

                default['name'] = _(
                    '%(name)s/%(number)s', name=self.name, number=self.sh_so_number)
                default['state'] = 'draft'
                default['origin'] = self.name
                default['sh_sale_order_id'] = self.id
                self.sh_so_number += 1

            self.copy(default=default)
            sh_child_so = self.env['sale.order'].search(
                [('sh_sale_order_id', '=', self.id)])
            self.sh_revision_so_id = [(6, 0, sh_child_so.ids)]
            if self.state in ['draft', 'sent']:
                self.action_cancel()
        return True

    def _compute_parent_view_btn(self):
        """This method is used to hide the parent button."""
        for rec in self:
            if rec.sh_sale_order_id:
                rec.parent_view_btn = False
            else:
                rec.parent_view_btn = True