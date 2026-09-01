# -*- coding: utf-8 -*-
{
    'name': 'manaTec Contact NDA',
    'summary': 'Tracks NDA validity on Contacts and reminds a responsible user before it expires',
    'description': 'Adds an NDA Valid Until date field to res.partner and a scheduled action that '
                    'creates a reminder activity a configurable number of months before expiry. The '
                    'months, activity type and default responsible user are configured as constants '
                    'directly in the scheduled action\'s code. The activity is assigned to the contact\'s '
                    'Salesperson or Buyer if exactly one of them is set, otherwise to the default user.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Sales/CRM',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'purchase',
        'mail',
    ],
    'data': [
        'views/res_partner_views.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
