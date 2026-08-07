# -*- coding: utf-8 -*-
{
    'name': 'manaTec Purchase Analytic Distribution Display',
    'summary': 'Adds analytic distribution display field to Purchase Order Line',
    'description': 'Extends purchase order line with analytic_account_display field and view integration.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Purchase Management',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'purchase',
        'manatec_analytic_distribution_display',
    ],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
