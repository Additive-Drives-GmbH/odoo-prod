{
    "name": "IFE Textblock Global",
    "version": "18.0.1.0.3",
    "author": "IFE Gesellschaft für Forschung und Entwicklung",
    "category": "Customizations/Reports",
    "website": "https://www.ife.de",
    "license": "LGPL-3",
    "summary": "Global Textblock",
    "depends": [
        "base",
        "web",
        "product",
        "sale",
    ],
    "data": [
        "security/textblock_security.xml",
        "security/ir.model.access.csv",
        "views/text_block_view.xml",
        "views/ir_model_views.xml",
        "views/product_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ife_textblock/static/src/css/li_style.css",
        ],
    },
    "installable": True,
    "application": True,
}
