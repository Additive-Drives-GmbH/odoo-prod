{
    "name": "IFE Textblock Repair",
    "version": "18.0.1.0.0",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Insert Textblock in Repair.",
    "depends": [
        "repair",
        "ife_textblock",
    ],
    "data": [
        "views/text_block_view.xml",
        "views/repair_view.xml",
        "report/repair_templates_repair_order.xml",
    ],
    "installable": True,
    "auto_install": True,
}
