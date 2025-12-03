# © 2025 syscoon GmbH (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Only process companies that have the finance interface feature enabled
    companies = env["res.company"].search(
        [("export_finance_interface_active", "=", False)]
    )
    _logger.info(
        "post_init: Start: Set visibility of Finance Interface Menu for %s companies",
        len(companies),
    )
    if companies:
        companies._set_visible_financeinterface_menu()
        _logger.info(
            "post_init: Successfully updated menu visibility for %s companies",
            len(companies),
        )
    else:
        _logger.info(
            "post_init: No companies found with finance interface feature enabled"
        )
    _logger.info("post_init: End")
