# -*- coding: utf-8 -*-
{
    'name': 'manaTec Purchase Employee',
    'summary': 'Extends Purchase with needed fields and views',
    'description': 'This module extends the Purchase functionality.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Purchase Management',
    'version': '18.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'base',
        'purchase',
        'hr'
    ],
    'data': [
        'views/hr_employee_views.xml',
        'views/purchase_order_views.xml',
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
