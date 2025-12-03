{
    "name": "IFE Textblock Model Option",
    "version": "18.0.1.0.0",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Add Possibility to render textblock template directly "
    "in report and specify position to show it either Pre or Post",
    "depends": [
        "ife_textblock",
        "ife_textblock_sale",
        "ife_textblock_invoice",
        "ife_textblock_stock",
    ],
    "data": [
        "views/text_block_views.xml",
        "report/sale_report_template.xml",
        "report/invoice_report_template.xml",
        "report/report_deliveryslip_template.xml",
        "report/report_stockpicking_operations.xml",
    ],
    "installable": True,
    "application": True,
}
