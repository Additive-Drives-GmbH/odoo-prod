{
    "name": "Additive Delivery Reports",
    "version": "18.0.1.0.0",
    "category": "Reporting",
    "summary": "Extend and Adjust Delivery Note Report",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "website": "https://www.ife.de",
    "license": "AGPL-3",
    "depends": [
        "stock",
        "sale_stock",
        "stock_delivery",
        "l10n_din5008_stock",
        "l10n_din5008",
        "syscoon_partner_accounts",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/report_deliveryslip.xml",
        "views/report_templates.xml",
    ],
}
