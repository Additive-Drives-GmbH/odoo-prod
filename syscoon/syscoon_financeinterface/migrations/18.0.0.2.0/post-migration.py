# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

from dateutil import parser
from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("post_init: Start")
    env = Environment(cr, SUPERUSER_ID, {})
    for record in env["syscoon.financeinterface"].search([]):
        vals = {"state": "export"}
        if record.period:
            period = record.period.split(" - ")
            if len(period) == 2:
                vals.update(
                    {
                        "start_date": parser.parse(period[0]),
                        "end_date": parser.parse(period[1]),
                    }
                )
            elif len(period) == 1:
                vals.update({"start_date": parser.parse(period[0])})
        record.write(vals)
    _logger.info("post_init: End")
