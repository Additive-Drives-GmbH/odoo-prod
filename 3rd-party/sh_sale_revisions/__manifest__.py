# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Sale Order Revision",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "license": "OPL-1",
    "category": "Sales",
    "summary": """Sales Order Revision, Sale Orders Revision, Sales Revision, Sale Order Revisions,
                Sales Quote Revision,Revision History,Revise Sale Order, Revision Quotation,
                Revision Order Of Sale,Generate Revision Order Sale Revision Sales
                Revision Odoo""",
    "description": """This module allows to create revision of the cancelled sale order/quotation
                    with the same base number. You can maintain a log of generated revisions. Which
                    can be useful to keep track of all sale order history.""",
    "version": "0.0.2",
    "depends": [
        "sale_management",
    ],
    "application": True,
    "data": [
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
    ],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price":13,
    "currency": "EUR"
}
