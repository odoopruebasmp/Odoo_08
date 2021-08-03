# -*- coding: utf-8 -*-
{
    'name': 'Factura Electrónica Avancys',
    'version': '1.0',
    'author': 'Avancys SAS',
    'website': 'www.avancys.com',
    'category': 'Accounting & Finance',
    'depends': ['inventory_account'],
    'summary': 'Control proceso generación Factura Electrónica',
    'description': '''
    - Facturacion electronica para Avancys SAS
    ''',
    'init_xml': [],
    'data': [
        'data/ei_cron.xml',
        'security/ei_security.xml',
        'security/ir.model.access.csv',
        'wizard/change_ei_state.xml',
        'wizard/generate_ei_xml.xml',
        'wizard/ei_batch_process.xml',
        'views/electronic_invoice.xml',
        'views/res_company.xml',
        'views/email_helper.xml',
        'views/customer_acknowledge.xml',
        'views/res_partner.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
