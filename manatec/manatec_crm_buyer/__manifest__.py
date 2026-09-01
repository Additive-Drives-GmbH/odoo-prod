# -*- coding: utf-8 -*-
{
    'name': 'manaTec CRM Buyer',
    'summary': 'Adds a Buyer contact field to the Lead/Opportunity Contact Information',
    'description': 'Extends crm.lead with a Buyer field linking to a res.partner contact record on the '
                    'customer side, plus a Buyer Email field for quick reference, shown in the Contacts '
                    'tab under Contact Information.',
    'author': "manaTec GmbH",
    'website': 'https://www.manatec.de',
    'support': 'info@manatec.de',
    'category': 'Sales/CRM',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': [
        'crm',
    ],
    'data': [
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
