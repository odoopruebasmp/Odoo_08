# -*- coding: utf-8 -*-

{
    'name': 'Payroll Extended MP',
    'category': 'Human Resources',
    'complexity': "Low",
    'description': """Este modulo realiza cambios en los prestamos de MP
    """,
    'author':'Avancys',
    'website':'www.avancys.com',
    'depends': [
        'hr_payroll_extended'
    ],
	'data': [
       'hr_payroll_extended_mp.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
