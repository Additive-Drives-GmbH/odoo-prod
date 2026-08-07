# -*- coding: utf-8 -*-
{
    'name': 'manaTec Analytic Distribution Display',
    'summary': 'Display mixin for analytic distribution in human-readable format',
    'description': 'Provides a mixin that resolves analytic_distribution JSON into a readable string and decimal precision configuration.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Accounting/Analytic',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'analytic',
    ],
    'data': [
        'data/decimal_precision_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
