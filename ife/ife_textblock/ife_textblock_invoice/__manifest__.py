{
    "name": "IFE Textblock Invoice",
    "version": "18.0.1.0.1",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Insert Textblock in Invoices",
    "depends": [
        "account",
        "ife_textblock",
    ],
    "data": [
        "views/account_move_view.xml",
        "views/text_block_view.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
    "auto_install": True,
}
