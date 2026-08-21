# -*- coding: utf-8 -*-
{
    'name': 'manaTec Sale Pre/Post Text',
    'summary': 'Adds Pre-Text and Post-Text tabs to the Sale Order form and report',
    'description': 'Extends sale.order with a Pre-Text HTML field printed before the product table '
                    '(both in the PDF report and the online quotation preview), and moves the Terms '
                    'and Conditions (AGB) field into its own Post-Text tab.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'sale',
    ],
    'data': [
        'views/sale_order_views.xml',
        'report/sale_report_templates.xml',
        'report/sale_portal_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
