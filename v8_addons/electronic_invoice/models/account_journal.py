# -*- coding: utf-8 -*-
from openerp import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    invoice_resolution = fields.Char(
        'Número de Resolución', help="Número de Resolución para Factura Electrónica")
    invoice_prefix = fields.Char(
        'Prefijo de Factura', help="Prefijo de Factura")
    ei_start_invoice = fields.Integer('Número Inicio de Factura', help="Número de Inicio de Facturación según "
                                                                       "Resolución para Facturación Electrónica")
    ei_end_invoice = fields.Integer('Número Fin de Factura', help="Número de Fin de Facturación según Resolución "
                                                                  "para Facturación Electrónica")
    ei_start_date = fields.Date(
        'Fecha Inicio Resolución', help="Fecha Inicio de Resolución")
    ei_end_date = fields.Date('Fecha Fin Resolución',
                              help="Fecha Fin de Resolución")
    ei_payment_method = fields.Integer(u'Método de Pago', size=2, default=30,
                                       help='Método de Pago especificado por el intermediario para '
                                            'Facturación Electrónica. Ver Tabla 5 en esquema de Diseño. '
                                            'Por defecto se lleva 30, equivalente a Transferencia Crédito')
    id_param = fields.Integer(string='ID Resolución')
    contingency_invoice = fields.Boolean(
        string='Facturas de Contingencia',
        help='Marque este check para indicar que el diario es para facturas de Contingencia')
