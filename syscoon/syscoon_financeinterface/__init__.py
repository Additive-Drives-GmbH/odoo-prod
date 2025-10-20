# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from . import models


import logging

_logger = logging.getLogger(__name__)


def _init_syscoon_financeinterface_export_sequence(env):
    _logger.info("post_init: Start: Create Export Sequence for Companies")
    companies = env["res.company"].search([])
    companies._update_existing_financeinterface_export_sequence()
    companies._create_financeinterface_export_sequence()
    _logger.info("post_init: End")
