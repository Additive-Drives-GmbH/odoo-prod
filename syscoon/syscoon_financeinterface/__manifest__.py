# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
{
    "name": "syscoon Financeinterface",
    "version": "18.0.1.0.6",
    "depends": ["account", "hr_expense", "syscoon_analytic_mixin", "syscoon_menu_rule"],
    "author": "syscoon Estonia OÜ",
    "license": "OPL-1",
    "website": "https://syscoon.com",
    "summary": "Main Module for export of accounting moves",
    "description": """The main modul syscoon_financeinterface provides the basic
        methods for finance exports to accounting software.""",
    "category": "Accounting/Accounting",
    "data": [
        "data/syscoon_financeinterface_template_data.xml",
        "reports/financeinterface_report.xml",
        "security/syscoon_financeinterface_security.xml",
        "security/ir.model.access.csv",
        "views/account_move.xml",
        "views/analytic_plan_views.xml",
        "views/syscoon_financeinterface.xml",
        "views/res_config_settings.xml",
        "views/syscoon_financeinterface_template_views.xml",
        "views/syscoon_financeinterface_bookingtext_views.xml",
        "views/menus_views.xml",
    ],
    "installable": True,
    "module_type": "official",
    "post_init_hook": "_init_syscoon_financeinterface_export_sequence",
}
