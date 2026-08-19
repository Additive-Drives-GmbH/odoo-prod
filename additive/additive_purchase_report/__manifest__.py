{
    "name": "Additive Purchase Report",
    "summary": "Purchase Report Customisations for Additive",
    "category": "Custom",
    "version": "19.0.1.0.6",
    "license": "LGPL-3",
    "author": "manaTec GmbH",
    "website": "https://www.manatec.de",
    "depends": [
        "purchase",
        "l10n_din5008_purchase",
        "project_purchase",
    ],
    "data": [
        "views/res_partner_views.xml",
        "report/l10n_din5008_purchase_templates.xml",
        "report/purchase_report_templates.xml",
    ],
    "auto_install": False,
    "installable": True,
}
