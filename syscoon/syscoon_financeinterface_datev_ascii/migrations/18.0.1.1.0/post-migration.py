# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime

from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("post_init: Start")
    env = Environment(cr, SUPERUSER_ID, {})

    # Get date from two weeks ago
    d20_april_2025 = datetime(2025, 4, 20)
    # Find moves created in the last two weeks
    moves = env["account.move"].search(
        [
            ("create_date", ">=", d20_april_2025),
            ("datev_ref", "in", ("", None, False)),
            ("state", "not in", ("draft", "cancel")),
        ]
    )

    if moves:
        _logger.info(
            "Recomputing datev_ref for %s moves created since %s",
            len(moves),
            d20_april_2025,
        )
        # Force recomputation of datev_data fields
        moves._assign_datev_values()
        _logger.info("Recomputation of datev_data completed")
    else:
        _logger.info("No moves found since %s", d20_april_2025)
