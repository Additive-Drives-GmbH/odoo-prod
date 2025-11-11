{
    "name": "Additive Reports",
    "summary": "Reports Customisations for Additive",
    "category": "Custom",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "website": "https://www.ife.de",
    "depends": [
        "l10n_din5008",
        "sale",
        "account",
        "sale_stock",
        "syscoon_partner_accounts",
    ],
    "data": [
        "report/l10n_din5008_templates.xml",
        "report/sale_report_templates.xml",
        "report/invoice_report_templates.xml",
        "views/res_company_views.xml",
        "views/res_bank_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "additive_reports/static/src/**/*",
        ],
    },
    "auto_install": False,
    "installable": True,
}
