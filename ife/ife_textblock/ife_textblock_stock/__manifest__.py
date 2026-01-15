{
    "name": "IFE Textblock Stock",
    "version": "18.0.1.0.1",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Insert Textblock in Delivery Orders.",
    "depends": [
        "stock",
        "ife_textblock",
    ],
    "data": [
        "views/stock_picking_form_view_ext.xml",
        "views/text_block_view.xml",
        "report/report_deliveryslip.xml",
        "report/report_stockpicking_operations.xml",
    ],
    "installable": True,
    "auto_install": False,
}
