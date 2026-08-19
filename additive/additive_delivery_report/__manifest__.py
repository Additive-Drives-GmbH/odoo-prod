{
    "name": "Additive Delivery Reports",
    "summary": "Extend and Adjust Delivery Note Report",
    "category": "Reporting",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "manaTec GmbH",
    "website": "https://www.manatec.de",
    "depends": [
        "stock",
        "sale_stock",
        "stock_delivery",
        "l10n_din5008_stock",
        "l10n_din5008",
    ],
    "data": [
        "report/stock_delivery_document_templates.xml",
        "report/stock_picking_din5008_layout_templates.xml",
    ],
    "auto_install": False,
    "installable": True,
}
