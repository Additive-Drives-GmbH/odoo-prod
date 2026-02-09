{
    "name": "IFE Textblock Purchase",
    "version": "18.0.1.0.2",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Insert Textblock in Purchase",
    "depends": [
        "purchase",
        "ife_textblock",
    ],
    "data": [
        "views/purchase_order_view.xml",
        "views/text_block_view.xml",
        "report/purchase_quotation_report.xml",
        "report/purchase_report.xml",
    ],
    "installable": True,
    "auto_install": True,
}
