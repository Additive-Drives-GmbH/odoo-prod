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
]

# Modules to install as part of the upgrade. Not listed in `depends` because
# some of them (e.g. manatec_html_editor_pagebreak, which depends on the
# 19.0-only `html_editor`) are not installable on the source (18.0) database,
# where this module itself must already be installed.
MODULES_TO_INSTALL = [
    "manatec_html_editor_pagebreak",
    "opd_integration",
    "manatec_sale_texts",
    "manatec_crm_buyer",
    "manatec_contact_nda"
]


def migrate(cr, version):
    # Remove obsolete view from additive_quotation_report that refers to removed field country_of_origin_id
    # This prevents errors when sale module is updated before additive_quotation_report
    _logger.info("Removing obsolete records from additive_quotation_report")
    util.remove_record(cr, "additive_quotation_report.view_sale_order_form_inherit")
    util.remove_record(cr, "additive_quotation_report.field_sale_order__country_of_origin_id")

    # Remove obsolete view from additive_reports that refers to removed field country_of_origin_id
    # This prevents errors when account module is updated before additive_reports
    _logger.info("Removing obsolete records from additive_reports")
    util.remove_record(cr, "additive_reports.view_account_move_form_inherit")
    util.remove_record(cr, "additive_reports.field_account_move__country_of_origin_id")
    util.remove_record(cr, "additive_reports.report_invoice_document_din5008_inherit")
    util.remove_record(cr, "additive_reports.view_partner_form_inherit")
    util.remove_record(cr, "additive_reports.field_res_partner__our_nr_by_customer")
    util.remove_record(cr, "additive_reports.field_res_partner__purchase_order_no")

    # Remove obsolete view from additive_delivery_report that refers to removed field purchase_order_no
    # This prevents errors when stock module is updated before additive_delivery_report
    _logger.info("Removing obsolete records from additive_delivery_report")
    util.remove_record(cr, "additive_delivery_report.view_partner_form_delivery_note")
    util.remove_record(cr, "additive_delivery_report.external_layout_delivery_title")
    util.remove_record(cr, "additive_delivery_report.field_res_partner__purchase_order_no")

    # Remove obsolete view from additive_purchase_report that refers to removed field disable_purchase_position_recompute
    # This prevents errors when purchase module is updated before additive_purchase_report
    _logger.info("Removing obsolete records from additive_purchase_report")
    util.remove_record(cr, "additive_purchase_report.view_res_config_settings_form")
    util.remove_record(cr, "additive_purchase_report.view_purchase_order_form_inherit")
    util.remove_record(cr, "additive_purchase_report.action_compute_purchase_position")
    util.remove_record(cr, "additive_purchase_report.field_res_company__disable_purchase_position_recompute")
    util.remove_record(cr, "additive_purchase_report.field_res_config_settings__disable_purchase_position_recompute")
    util.remove_record(cr, "additive_purchase_report.field_purchase_order__locked_positions")
    util.remove_record(cr, "additive_purchase_report.field_purchase_order_line__position")
    util.remove_record(cr, "additive_purchase_report.field_purchase_order_line__position_formatted")

    # Special handling for stock_picking_report_custom_description
    # Using util.remove_module caused a MissingError because Odoo.sh attempts to update it
    # despite it being removed. We set it to 'to remove' instead of deleting the record.
    _logger.info("Setting module stock_picking_report_custom_description to 'to remove'")
    cr.execute(
        "UPDATE ir_module_module SET state='to remove' "
        "WHERE name='stock_picking_report_custom_description' AND state != 'uninstalled'"
    )

    for module in MODULES_TO_REMOVE:
        _logger.info("Removing module %s", module)
        util.remove_module(cr, module)

    for module in MODULES_TO_INSTALL:
        _logger.info("Installing module %s", module)
        util.force_install_module(cr, module)
