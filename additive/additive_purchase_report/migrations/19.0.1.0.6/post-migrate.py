import logging
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Activating view additive_purchase_report.report_purchaseorder_document_inherit")
    cr.execute(
        """
        UPDATE ir_ui_view
        SET active = true
        FROM ir_model_data
        WHERE ir_ui_view.id = ir_model_data.res_id
          AND ir_model_data.model = 'ir.ui.view'
          AND ir_model_data.module = 'additive_purchase_report'
          AND ir_model_data.name = 'report_purchaseorder_document_inherit'
    """
    )
