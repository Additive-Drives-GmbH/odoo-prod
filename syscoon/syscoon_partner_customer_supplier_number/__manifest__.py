# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
{
    "name": "syscoon Partner Customer and Supplier Number ",
    "summary": "syscoon Partner Customer and Supplier Number ",
    "description": """
App adds two fields for external customer and supplier number inside res.partner.
There is the possibility, when activated in the settings,
that the customer number appears on invoices and refunds.
    """,
    "author": "syscoon Estonia OÜ",
    "license": "OPL-1",
    "website": "https://syscoon.com",
    "category": "Accounting",
    "version": "18.0.1.0.0",
    "depends": [
        "l10n_din5008",
        "sale",
        "purchase",
    ],  # depends on l10n_din5008 bc of the invoice reports
    "data": [
        "security/ir.model.access.csv",
        "data/automatic_mode.xml",
        "views/res_partner_view.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "module_type": "official",
}
