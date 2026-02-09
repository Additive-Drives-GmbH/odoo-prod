{
    "name": "IFE Textblock Sale",
    "version": "18.0.1.0.3",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Insert Textblock in Sales",
    "depends": [
        "sale_management",
        "sale",
        "ife_textblock",
    ],
    "data": [
        "views/sale_order_view.xml",
        "views/sale_order_template_views.xml",
        "views/text_block_view.xml",
        "report/sale_report_template.xml",
        "report/sale_portal_templates.xml",
    ],
    "installable": True,
    "auto_install": True,
}
