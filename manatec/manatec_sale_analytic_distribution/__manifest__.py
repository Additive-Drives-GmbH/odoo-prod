# -*- coding: utf-8 -*-
{
    'name': 'manaTec Sale Analytic Distribution Display',
    'summary': 'Adds analytic distribution display field to Sale Order Line',
    'description': 'Extends sale order line with analytic_account_display field and view integration.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'sale',
        'manatec_analytic_distribution_display',
    ],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
