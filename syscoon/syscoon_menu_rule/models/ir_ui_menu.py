# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import api, models, tools
from odoo.http import request


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    @tools.ormcache("frozenset(self.env.user.groups_id.ids)", "debug")
    def _visible_menu_ids(self, debug=False):
        """
        Return the ids of menu items that should be visible for the current company,
        taking into account the company-specific menu restrictions.
        """
        # Get the base visible menu ids from parent class
        visible = super()._visible_menu_ids(debug=debug)
        return visible - set(self._restricted_menus())

    def _restricted_menus(self):
        """
        Return the ids of menu items that should be hidden for the current company,
        taking into account the company-specific menu restrictions.
        """
        company = self._active_company()
        return company.restrict_menu_ids.ids if company else []

    def blacklisted_menu_ids(self):
        blocked_menus = super().blacklisted_menu_ids()
        return blocked_menus + self._restricted_menus()

    def _active_company(self):
        cids = request and request.httprequest.cookies.get("cids")
        if cids:
            cids = [int(cid) for cid in cids.split("-")]
        return (
            self.env["res.company"].browse(cids[0])
            if cids and all(cid in self.env.user.company_ids.ids for cid in cids)
            else self.env.user.company_id
        )
