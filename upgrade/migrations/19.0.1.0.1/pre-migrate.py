import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# `util.remove_module` only removes the named module itself, it does not
# follow the dependency graph to remove modules that depend on it. List
# dependents before the module they depend on, so each module's own
# records/views/menus are cleaned up before the module providing their
# base models disappears.
MODULES_TO_REMOVE = [
    "ife_textblock_invoice",
    "ife_textblock_model_option",
    "ife_textblock_proforma",
    "ife_textblock_purchase",
    "ife_textblock_repair",
    "ife_textblock_sale",
    "ife_textblock_stock",
    "ife_textblock",
    "account_move_tier_validation",
    "purchase_tier_validation",
    "base_tier_validation",
    "crm_project_create",
    "mail_message_destiny_link_template",
    "project_template",
    "stock_picking_report_custom_description",
]

# Modules to install as part of the upgrade. Not listed in `depends` because
# some of them (e.g. manatec_html_editor_pagebreak, which depends on the
# 19.0-only `html_editor`) are not installable on the source (18.0) database,
# where this module itself must already be installed.
MODULES_TO_INSTALL = [
    "manatec_html_editor_pagebreak",
    "opd_integration",
]


def migrate(cr, version):
    # Remove obsolete view from additive_quotation_report that refers to removed field country_of_origin_id
    # the view gets called, before the module gets removed, so we do it "manually" beforehand
    # This prevents errors when sale module is updated before additive_quotation_report
    _logger.info("Removing obsolete records from additive_quotation_report")
    util.remove_record(cr, "additive_quotation_report.view_sale_order_form_inherit")
    util.remove_record(cr, "additive_quotation_report.field_sale_order__country_of_origin_id")

    for module in MODULES_TO_REMOVE:
        _logger.info("Removing module %s", module)
        util.remove_module(cr, module)

    for module in MODULES_TO_INSTALL:
        _logger.info("Installing module %s", module)
        util.force_install_module(cr, module)
