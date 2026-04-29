# -*- coding: utf-8 -*-
{
    'name': 'manaTec Purchase Report',
    'summary': 'Extends Purchase Report with origin field',
    'description': 'This module extends the Purchase DIN 5008 report by adding the origin field to the information block.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Purchase Management',
    'version': '18.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'purchase',
        'l10n_din5008_purchase',
    ],
    'data': [
        'report/purchase_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
