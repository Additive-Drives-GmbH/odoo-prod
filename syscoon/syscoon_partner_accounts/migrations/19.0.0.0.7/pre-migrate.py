# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def _unlink_view_recursive(env, view):
    """Recursively unlink a view and all its children (leaf to root)."""
    if not view:
        return
    # Find all child views that inherit from this view
    children = env["ir.ui.view"].search([("inherit_id", "=", view.id)])
    # Recursively delete children first
    for child in children:
        _unlink_view_recursive(env, child)
    # Now safe to delete this view
    view.unlink()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref(
        "syscoon_partner_accounts.res_config_settings_view_form",
        raise_if_not_found=False,
    )
    _unlink_view_recursive(env, view)
