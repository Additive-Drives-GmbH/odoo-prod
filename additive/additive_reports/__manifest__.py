{
    "name": "Additive Reports",
    "summary": "Reports Customisations for Additive",
    "category": "Custom",
    "version": "19.0.1.0.10",
    "license": "LGPL-3",
    "author": "manaTec GmbH",
    "website": "https://www.manatec.de",
    "depends": [
        "web",
        "l10n_din5008",
        "account",
        "stock_delivery"
    ],
    "data": [
        "report/l10n_din5008_templates.xml",
        "report/invoice_report_templates.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "additive_reports/static/src/**/*",
        ],
    },
    "auto_install": False,
    "installable": True,
}
