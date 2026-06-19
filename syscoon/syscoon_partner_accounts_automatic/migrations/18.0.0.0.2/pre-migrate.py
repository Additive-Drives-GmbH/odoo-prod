# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api


def _unlink_view_recursive(view):
    """Recursively unlink a view and all its children (leaf to root)."""
    if not view:
        return
    # Delete child views first via the inherit_children_ids relation. Pass
    # active_test=False so inactive children are included too — otherwise they
    # are silently skipped and then violate the inherit_id FK on the unlink.
    for child in view.with_context(active_test=False).inherit_children_ids:
        _unlink_view_recursive(child)
    # Now safe to delete this view
    view.unlink()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref(
        "syscoon_partner_accounts_automatic.res_config_settings_view_form",
        raise_if_not_found=False,
    )
    _unlink_view_recursive(view)
