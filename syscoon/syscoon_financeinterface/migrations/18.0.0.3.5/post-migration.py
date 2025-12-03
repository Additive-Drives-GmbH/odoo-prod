# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("post_init: Start: Create Export Sequence for Companies")
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env["res.company"].search([])
    companies._update_existing_financeinterface_export_sequence()
    companies._create_financeinterface_export_sequence()
    _logger.info("post_init: End")
