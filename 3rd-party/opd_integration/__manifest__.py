# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Advanced Pipedrive Integration | Odoo Pipedrive Connector',
    'version': '19.0.0.1',
    'summary': (
        'Odoo Pipedrive Integration | Odoo Pipedrive Connector | Pipedrive Odoo Integration App | '
        'Bi-Directional Sync | CRM Integration | Lead Sync | Deal Sync | Opportunity Sync | '
        'Organizations Sync | Persons Sync | Activities Sync | Notes Sync | Files Sync | pipedrive connector'
        'Products Sync | Pipedrive API v2 | Custom Field Mapping | Scheduled Sync | Pipedrive CRM'
    ),
    'sequence': '-101',
    'price': '149.00',
    'currency': 'USD',
    'maintainer': 'echoBitz IT Solutions Pvt. Ltd.',
    'author': 'echoBitz IT Solutions Pvt. Ltd.',
    'description': """
        -Odoo Pipedrive Integration
        -================================
        -<keywords>
        -Pipedrive Odoo Integration App
        -Pipedrive
        -Pipedrive odoo 
        -Pipedrive CRM
        -odoo Pipedrive connector
        -odoo Pipedrive integration
        -crm app
        -crm conncetor
        -""",
    'live_test_url': 'https://calendly.com/echobitzit-info/45min?back=1',
    'website': 'https://www.echobitzit.com',
    'category': 'Integration',
    'depends': ['base', 'mail', 'crm', 'web', 'stock', 'account', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'security/opd_security.xml',
        'data/opd_integration_cron.xml',
        'views/opd_menu.xml',
        'wizard/opd_manual_record_pipedrive_to_odoo.xml',
        'wizard/opd_manual_partner_record_pipedrive_to_odoo.xml',
        'wizard/opd_manual_crm_record_pipedrive_to_odoo.xml',
        'wizard/opd_manual_product_record_pipedrive_to_odoo.xml',
        'wizard/opd_manual_user_record_pipedrive_to_odoo.xml',
        'views/opd_pipedrive_instance_view.xml',
        'views/opd_contact_mapper_view.xml',
        'views/opd_company_mapper_view.xml',
        'views/opd_lead_mapper_view.xml',
        'views/opd_deal_mapper_view.xml',
        'views/opd_product_mapper_view.xml',
        'views/opd_activity_mapper_view.xml',
        'views/opd_res_partner_view.xml',
        'views/opd_crm_lead_view.xml',
        'views/opd_product_template_view.xml',
        'views/opd_activities_view.xml',
        'views/opd_res_user_view.xml',
        'views/opd_logger_view.xml',
        'views/opd_filters_views.xml'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'images': ['static/description/banner.gif'],
    'license': 'OPL-1',
}
