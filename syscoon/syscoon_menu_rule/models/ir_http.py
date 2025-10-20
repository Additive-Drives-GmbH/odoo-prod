# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        company = self.env["ir.ui.menu"]._active_company()
        if str(company.id) != request.session.get("active_cid", "0"):
            self.env["ir.ui.menu"].clear_caches()
        request.session["active_cid"] = str(company.id)
        return super().session_info()
