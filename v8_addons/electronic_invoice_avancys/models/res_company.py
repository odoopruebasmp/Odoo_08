# -*- coding: utf-8 -*-
from openerp import models, fields, api
from http_helper import DEFAULT_SERVICE_URL
from http_helper import DEFAULT_SERVICE_URL_GET
from http_helper import DEFAULT_SERVICE_POST


class ResCompany(models.Model):
    _inherit = 'res.company'

    electronic_invoice = fields.Boolean('Gestión de Factura Electrónica', help='POLÍTICA A NIVEL DE COMPAÑÍA, '
                                        'AFECTACIÓN EN PROCESOS DE FACTURACIÓN. Marque esta casilla si quiere '
                                        'habilitar la Facturación Electrónica.', default=True)
    ei_database = fields.Char(string='Base de Datos', default=lambda self: self.env.cr.dbname,
                              required=True, help='Base de Datos en la cual funcionará la Facturación Electrónica')
    ei_server_type = fields.Selection([('production', u'Producción'), ('test', 'Pruebas')],
                                      string='Ambiente', default='test', required=True,
                                      help='Indicador del tipo de ambiente de Facturación Electrónica que se usará en '
                                           'esta Base de Datos')
    ei_automatic_gen = fields.Boolean('Tarea Automática Generación', help='Marque este check si quiere permitir la '
                                      'ejecución de la tarea automática de generación de Factura Electrónica para '
                                      'aquellas Facturas/Notas Crédito-Débito que apliquen.', default=True)
    ei_automatic_read = fields.Boolean('Tarea Automática Lectura', help='Marque este check si quiere permitir la '
                                       'ejecución de la tarea automática de lectura de archivos relacionados a la '
                                       'Factura Electrónica.', default=True)
    # Servidor
    service_url = fields.Char(
        'URL Servicio',
        help='URL de envio de Facturación Electrónica del Proveedor',
        default=DEFAULT_SERVICE_URL)
    service_url_get = fields.Char(
        'URL Respuesta',
        help='URL de Respuesta de Proveedor',
        default=DEFAULT_SERVICE_URL_GET)
    service_url_post = fields.Char(
        'URL Peticion',
        help='URL de envio de Facturación Electrónica del Facturador',
        default=DEFAULT_SERVICE_POST)
    software_code = fields.Char(
        'Token', help='Token de Proveedor Tecnológico')
    ei_temporal_files = fields.Char('Dirección local transferencia', help='Directorio temporal de transferencia de '
                                                                          'archivos en el servidor local')
    # XML Factura
    xml_automatic_generation = fields.Boolean('Envio Automático de Factura', help='POLÍTICA A NIVEL DE COMPAÑÍA, '
                                              'AFECTACIÓN EN EL PROCESO DE GENERACIÓN DEL XML DE FACTURACIÓN '
                                              'ELECTRÓNICA. Marque esta casilla si quiere que el xml de factura '
                                              'electrónica se genere automáticamente al validar las facturas. '
                                              'Este proceso de generación es independiente al de validación de la '
                                              'factura.')
    send_cus_po = fields.Boolean('Envío OC Cliente', help='Marque esta casilla si quiere permitir el envío del archivo '
                                                          'de órden de compra del cliente, adjunto en el XML de FE')
    send_remission = fields.Boolean('Envío Remisión', help='Marque esta casilla si quiere permitir el envío del '
                                                           'archivo de Remisíon, adjunto en el XML de FE')
    send_cus_att = fields.Boolean('Envío Adjuntos Factura', help='Marque esta casilla si quiere permitir el envío de '
                                  'archivos adjunto de FE desde la vista formulario de las Facturas de Venta y '
                                  'Notas Crédito/Débito de Cliente')
    ei_operation_type = fields.Selection([('09', 'AIU'), ('10', 'Estandar'),
                                          ('11', 'Mandatos')],
                                         string='Operación Principal', required=True, default='10',
                                         help='Tipo de Operación principal de la compañía, información necesaria para '
                                              'campo ENC_21 en XML de Facturación Electrónica')
    ei_pdf_template = fields.Char(
        string='Formato de factura', help='ID externo de formato de factura',
        default='reportes_avancys.report_facturas')
    attach_invoice_xml = fields.Boolean('Adjuntar XML Facturación', help='Marque esta casilla para adjuntar en el '
                                        'documento factura del sistema, la representación en formato XML de la Factura '
                                        'Electrónica.', default=True)
    auto_acceptance_email = fields.Boolean(string='Envio automático de Email')
    ei_prefixes = fields.Char(
        string='Prefijos de Facturas', help='Prefijos de facturas separados por ;')
    withholding_report = fields.Boolean(
        string='Reportar retenciones',
        help='La retenciones no contribuyen al valor a pagar de la factura\
            ante la DIAN, Sin embargo pueden ser enviadas para que aparezcan\
            de manera informativa en el PDF'
    )
    auto_acceptance_email = fields.Boolean(
        string='Envio automático de Email de Aceptación')
    invoice_batch_process = fields.Boolean(
        string='Envio Masivo de facturas', default=False)
    mail_server_id = fields.Many2one(
        comodel_name='ir.mail_server', string='Servidor Email Preferido')
    tributary_obligations = fields.Char(
        string='Obligaciones Tributarias',
        help='Usadas en la construcción del XML AttachedDocument',
        default='R-99-PN')
