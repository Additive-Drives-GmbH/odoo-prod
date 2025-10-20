# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
{
    "name": "syscoon Finanzinterface - DATEV ASCII Export",
    "version": "18.0.1.1.7",
    "author": "syscoon Estonia OÜ",
    "license": "OPL-1",
    "website": "https://syscoon.com",
    "summary": "DATEV ASCII Export ",
    "description": """The module account_financeinterface_datev provides the DATEV ASCII Export.""",
    "category": "Accounting/Accounting",
    "depends": [
        "syscoon_financeinterface",
        "syscoon_partner_accounts",
    ],
    "data": [
        "data/ir_actions_server.xml",
        "views/account_journal.xml",
        "views/account_move_views.xml",
        "views/account_payment_term.xml",
        "views/account_views.xml",
        "views/res_config_settings.xml",
        "views/syscoon_financeinterface.xml",
    ],
    "installable": True,
    "module_type": "official",
}
