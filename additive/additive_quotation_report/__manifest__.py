{
    "name": "Additive Quotation Report",
    "summary": "Quotation Report Customisations for Additive",
    "category": "Custom",
    "version": "18.0.1.0.3",
    "license": "LGPL-3",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "website": "https://www.ife.de",
    "depends": [
        "account",
        "sale",
        "sale_order_line_position",
        "additive_reports",
        "sale_stock",
    ],
    "data": [
        "report/sale_report_templates.xml",
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "additive_quotation_report/static/src/**/*",
        ],
    },
    "auto_install": False,
    "installable": True,
}
