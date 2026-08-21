# -*- coding: utf-8 -*-
{
    'name': 'manaTec Sale Texts',
    'summary': 'Adds Pre-Text and reorganizes Terms and conditions on Sale Order',
    'description': 'Adds a Pre-Text HTML field to sale.order, shown before the order '
                    'lines table in the report and portal, and moves Pre-Text/Terms and '
                    'conditions into dedicated notebook tabs on the order form.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Sales/Sales',
    'version': '18.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'sale',
    ],
    'data': [
        'views/sale_order_views.xml',
        'views/sale_order_portal_templates.xml',
        'report/sale_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
