# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)

XMLID = "syscoon_financeinterface.syscoon_financeinterface_main_template_line_115"
OLD_EXPR = "^((0[1-9]|[1-2]\\d|3[0-1])(0[1-9]|1[0-2])([2])([0])(\\d{2}))$"
NEW_EXPR = "^((?:0[1-9]|[1-2]\\d|3[0-1])(?:0[1-9]|1[0-2])(?:[2])(?:[0])(?:\\d{2}))$"


def migrate(cr, version):
    """Fix Leistungsdatum template regex to use non-capturing groups.

    The original regex used nested capturing groups which caused the
    _apply_regex_config method to duplicate the date value when
    concatenating all group matches (e.g. '1803202618032026' instead
    of '18032026'). This replaces inner groups with non-capturing
    (?:...) syntax so only the outermost group is captured.
    """
    _logger.info("post-migration: Fix Leistungsdatum regex expression")
    cr.execute(
        """
        UPDATE syscoon_financeinterface_template_line
        SET expression = %s
        WHERE id = (
            SELECT res_id FROM ir_model_data
            WHERE module = 'syscoon_financeinterface'
            AND name = 'syscoon_financeinterface_main_template_line_115'
            AND model = 'syscoon.financeinterface.template.line'
        )
        AND expression = %s
        """,
        (NEW_EXPR, OLD_EXPR),
    )
    _logger.info("post-migration: Updated %d record(s)", cr.rowcount)
