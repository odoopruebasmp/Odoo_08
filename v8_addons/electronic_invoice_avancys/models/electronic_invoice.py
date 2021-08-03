# -*- coding: utf-8 -*-
import os
import re
import shutil
import paramiko
import zipfile
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import logging
from openerp import models, fields, api
from openerp.addons import decimal_precision as dp
from openerp.addons.avancys_tools import report_tools
from openerp.tools import config
from openerp.exceptions import Warning
from itertools import groupby
from http_helper import HEADERS
from http_helper import INVOICE
from http_helper import URL_XML
from copy import deepcopy as dpc
import base64
import json
import requests
import qrcode
import cStringIO

# Warnings
WRONG_DB_MATCH_WARNING = """
No es posible generar la representación XML Electrónica, verifique que la compañía tenga
habilitado el check de Facturación Electrónica y que la base de datos sea la correcta"""

ENV_MISSING_WARNING = """
Debe configurarse en la Compañía el tipo de Ambiente para Facturación Electrónica,
contacte a Soporte"""

OP_TYPE_MISSING_WARNING = """
Debe parametrizar en la Compañía el Tipo de Operación, campo necesario para
Facturación Electrónica, contacte a Soporte"""

# logging
_logger = logging.getLogger(__name__)


class EiOrderLog(models.Model):
    _name = 'ei.order.log'
    _inherit = 'mail.thread'
    _order = 'transaction_date desc'

    name = fields.Char('Referencia', readonly=True,
                       help='Numero de referencia del archivo')
    transaction_date = fields.Datetime(
        'Fecha de la Transacción', readonly=True, help='Fecha de la Transacción')
    name_file = fields.Char('Nombre del Archivo',
                            readonly=True, help="Nombre del Archivo")
    type_log = fields.Selection([('txt', 'Archivo Txt'), ('xml', 'Archivo Xml'), ('logxml', 'Log XML'),
                                 ('logpdf', 'Log PDF'), ('loghost',
                                                         'Error de Conexion'), ('cancel', 'Cancelado'),
                                 ('param', 'Parametrización'), ('none', 'No Aplica'), ('json', 'Archivo Json')],
                                string='Tipo Registro', readonly=True)
    type_doc = fields.Selection([('lg', 'Log Error'), ('ad', 'Adjunto'), ('rn', 'Aviso de Recibo'),
                                 ('nc', 'Nota Crédito'), ('nd',
                                                          'Nota Débito'), ('ei', 'Factura Electronica'),
                                 ('dr', 'Rechazado DIAN'), ('da',
                                                            'Aceptado DIAN'), ('ak', 'Acuse de Recibo'),
                                 ('ds', 'Aceptación/Rechazo')], string='Tipo Documento', readonly=True)
    description = fields.Text('Descripción', readonly=True, required=True)
    data = fields.Text('Contenido', readonly=True)
    state = fields.Selection([('open', 'Abierto'), ('close', 'Cerrado')], string='Estado', track_visibility='onchange',
                             readonly=True)
    document_state = fields.Selection([('pending', 'No Transferido'), ('done', 'Emitido'),
                                       ('supplier_rejec', 'Rechazado PT'), (
                                           'supplier_accep', 'Aceptado PT'),
                                       ('dian_rejec', 'Rechazado DIAN'), ('dian_accep',
                                                                          'Aceptado DIAN'),
                                       ('ack_cus', 'Recibido Cliente'), ('cus_rejec',
                                                                         'Rechazado Cliente'),
                                       ('cus_accep', 'Aceptado Cliente')], string='Estado Documento', readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Factura', readonly=True)
    picking_id = fields.Many2one('stock.picking', 'Remision', readonly=True)

    @api.multi  # TODO
    def chg_state(self):
        self.state = 'close' if self.state == 'open' else 'open'


class ResDocumentType(models.Model):
    _name = "res.document.type"
    _inherit = "res.document.type"

    ei_code = fields.Char('Codigo FE', size=2)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_po = fields.Binary(
        'OC Cliente', help='Archivo órden de compra cliente', copy=False)
    cus_po_name = fields.Char('Nombre OC Cliente', copy=False)
    pol_send_cus_po = fields.Boolean(
        'Política Envío OC', related='company_id.send_cus_po', readonly=True)

    @api.multi
    def write(self, vals):
        if 'customer_po' in vals and vals['customer_po']:
            self.env['account.invoice']._check_file_size(
                vals['cus_po_name'], vals['customer_po'])
        return super(SaleOrder, self).write(vals)

    @api.model
    def create(self, vals):
        if 'customer_po' in vals and vals['customer_po']:
            self.env['account.invoice']._check_file_size(
                vals['cus_po_name'], vals['customer_po'])
        return super(SaleOrder, self).create(vals)


class ProductUom(models.Model):
    _inherit = 'product.uom'

    ei_uom_code = fields.Char(
        'Código FE', help="Codigo de Unidad de Medida para Facturación Electronica.")


class AccountTaxCode(models.Model):
    _inherit = 'account.tax.code'

    ei_code = fields.Char('Codigo Factura Electronica',
                          help="Codigo de Impuesto para Facturación Electrónica")


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    @api.model
    def create(self, vals):
        if 'name' in vals and len(vals['name'] or '') > 35:
            raise Warning(u"El Lote '{}' no cumple con la longitud máxima permitida para facturación electrónica."
                          u"\n\nLongitud enviada {}\nLongitud permitida 35"
                          .format(vals['name'], len(vals['name'])))
        res = super(StockProductionLot, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if 'name' in vals and len(vals['name'] or '') > 35:
            raise Warning(u"El Lote '{}' no cumple con la longitud máxima permitida para facturación electrónica."
                          u"\n\nLongitud enviada {}\nLongitud permitida 35"
                          .format(vals['name'], len(vals['name'])))
        res = super(StockProductionLot, self).write(vals)
        return res


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    TAX_MAP = {
        '01': 'IVA',
        '02': 'IC',
        '03': 'ICA',
        '04': 'INC',
        '05': 'ReteIVA',
        '06': 'ReteFuente',
        '07': 'ReteICA'
    }

    @api.multi
    def _is_withholding(self, code):
        return code in ['05', '06', '07', '01C', '02C', '03C']

    @api.multi
    def _create_ei_order_log(self, inv, fname, tl, td, dct, data, st, dst, ol_nam=''):
        self.env['ei.order.log'].sudo().create({
            'name': inv.number if inv and not ol_nam else ol_nam,
            'transaction_date': datetime.now(),
            'name_file': fname,
            'type_log': tl,
            'type_doc': td,
            'description': dct,
            'data': data,
            'state': st,
            'document_state': dst,
            'invoice_id': inv if inv and isinstance(inv, int) else None if not inv else inv.id
        })

    # FE Nacional y de Exportación, Nota Crédito y Nota Débito
    @api.multi
    def generate_electronic_invoice(self):
        company = self.company_id
        if not company.electronic_invoice or company.ei_database != self._cr.dbname:
            raise Warning(WRONG_DB_MATCH_WARNING)
        if not company.ei_server_type:
            raise Warning(ENV_MISSING_WARNING)
        if not company.ei_operation_type:
            raise Warning(OP_TYPE_MISSING_WARNING)
        for inv in self:
            if inv.type not in ['out_invoice', 'out_refund']:
                continue
            if inv.ei_state in ('dian_accep', 'cus_accep', 'cus_rejec'):
                continue
            self.send_invoice(inv)
            if inv.ei_state != 'dian_accep':
                continue
            inv.create_token()
            if not company.auto_acceptance_email:
                continue
            inv.send_acknowlegement_email()

    def _get_invoice_reference(self, inv):
        picking = getattr(inv, 'stock_picking_id', False)
        if not picking:
            return inv.invoice_out_refund_id
        origin_picking = self.env['stock.picking'].search(
            [('name', '=', picking.origin)])
        origin_invoice = origin_picking.picking_invoice_id if origin_picking else False

        return origin_invoice or inv.invoice_out_refund_id

    def _get_invoice_json(self, inv):
        company = self.company_id
        co_partner = company.partner_id
        inv_partner = inv.partner_id
        journal = inv.journal_id
        tp = 'ei' if (inv.type == 'out_invoice' and journal.type ==
                      'sale') else 'nc' if inv.type == 'out_refund' else 'nd'
        # if inv.journal_id.contingency_invoice:
        #     tp = 'ct'
        if not journal.id_param:
            dct = 'No es posible generar el XML de FE del documento ' + inv.number + '. Por favor revise la ' \
                u'parametrización de Facturación Electrónica del Comprobante relacionado'
            inv._create_ei_order_log(
                inv, '', 'param', tp, dct, '', 'open', inv.ei_state)

        param_logs = inv.ei_order_log_ids.filtered(
            lambda x: x.type_log == 'param' and x.state == 'open')
        if param_logs:
            param_logs.write({'state': 'close'})

        if tp == 'ei':
            if not journal.ei_payment_method:
                raise Warning(u"Debe definir el códido del Método de Pago para facturación electrónica en el "
                              u"Diario %s, por favor ajustar." % journal.name)
        if tp == 'nc':
            reference = self._get_invoice_reference(inv)
            cude = reference.ei_cufe if reference else ''
            date_reference = reference.date_invoice if reference else ''
        if tp == 'nd':
            reference = inv.invoice_out_add_id or False
            cude = reference.ei_cufe if reference else ''
            date_reference = reference.date_invoice if reference else ''
        utc_adj = '-05:00'
        hora = str(datetime.strptime(inv.create_date,
                                     "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))[11:] + utc_adj
        currency_name = inv.currency_id.name
        ncnd = "enabled" if tp in ('nc', 'nd') else "disabled"
        id_param_ncnd = '0'
        if ncnd == "enabled":
            if not reference:
                raise Warning(
                    'No se encontró una factura electronica a rectificar valida')
            if reference.ei_state == 'dian_rejec':
                raise Warning(
                    'La factura electronica a rectificar %s no se encuentra aceptada por la DIAN' % reference.number)
            id_param_ncnd = str(inv.journal_id.id_param or 0)

        datos_conexion = {
            "token": company.software_code,
            "documento": co_partner.ref,
            "dv": str(co_partner.dev_ref),
            "id_cabecera": "0",
            "id_usuario": "1"
        }
        inv_type_map = {
            "nc": "91",
            "nd": "92",
            "ei": "01",
            "ct": "03"
        }
        inv_type = inv_type_map[tp]
        tipo_documento = {
            "numero": inv_type
        }
        basicos_factura = {
            "consecutivo": inv.number.replace(journal.sequence_id.prefix, ''),
            "moneda": currency_name,
            "tipo_operacion": company.ei_operation_type,
            "fecha_factura": inv.date_invoice,
            "hora_factura": hora
        }
        respuesta = {
            "ruta_post": company.service_url_post,
            "ruta_get": company.service_url_get,
            "metodo": "ajax",
            "extra1": "",
            "extra2": ""
        }
        if ncnd == "enabled":
            param_basico_id_param = id_param_ncnd
        else:
            param_basico_id_param = str(journal.id_param or 0)
        param_basico = {
            "id_param": param_basico_id_param,
            "test": "0",
            "ambiente": "1" if company.ei_server_type == 'production' else "2",
            "ruta_to_soap": ("SendBillSync"
                             if company.ei_server_type == 'production'
                             else "SendTestSetAsync")
        }
        facturador = {
            "ProviderID": co_partner.ref,
            "dv": str(co_partner.dev_ref)
        }
        autorizacion_descarga = {
            "activo": "enabled",
            "numero_documento": "",
            "dv": "",
            "tipo_documento": co_partner.ref_type.ei_code
        }
        WithholdingTaxTotal = {
            "aplica": "0"
        }

        def is_colombia(country_code):
            return country_code == "CO" or country_code == "169"
        co_partner_country = co_partner.country_id.code
        sale_order = inv.get_sale_orders()
        datos_empresa = {
            "Pais": "CO" if is_colombia(co_partner_country) else co_partner_country,
            "departamento": co_partner.state_id.code,
            "municipio": co_partner.state_id.code + co_partner.city_id.code,
            "direccion": co_partner.street,
            "nombre_sucursal": sale_order[0].warehouse_id.name if sale_order else (co_partner.city_id.name or co_partner.name)
        }
        partner_country = inv_partner.country_id.code
        datos_cliente = {
            "tipo_persona": "1",
            "Pais": partner_country,
            "municipio": (str(inv_partner.state_id.code) + str(inv_partner.city_id.code)
                          if is_colombia(partner_country) else ""),
            "numero_documento": inv_partner.ref,
            "dv": inv_partner.dev_ref,
            "tipo_documento": inv_partner.ref_type.ei_code,
            "departamento": inv_partner.state_id.code if is_colombia(partner_country) else "",
            "direccion": inv_partner.street,
            "nombre_sucursal": "",
            "RUT_nombre": inv_partner.name or 'Receptor',
            "RUT_pais": partner_country,
            "RUT_departamento": co_partner.state_id.code if is_colombia(partner_country) else "",
            "RUT_municipio": (str(inv_partner.state_id.code) + str(inv_partner.city_id.code)
                              if is_colombia(partner_country) else ""),
            "RUT_direcci\u00f3n": inv_partner.street,
            "RUT_impuesto": "01",
            "Respon_fiscales": "",
            "Num_matricula_mercantil": "",
            "Nombre_contacto": inv_partner.name,
            "Tel_contacto": inv_partner.phone,
            "Correo_contacto": inv_partner.email,
            "Nota_contacto": ""
        }
        datos_transportadora = {
            "active": "disabled",
            "tipo_persona": "1",
            "Pais": "",
            "municipio": "",
            "numero_documento": "",
            "dv": "",
            "tipo_documento": "",
            "departamento": "",
            "direccion": "",
            "nombre_sucursal": "",
            "RUT_nombre": "",
            "RUT_pais": "",
            "RUT_departamento": "",
            "RUT_municipio": "",
            "RUT_direcci\u00f3n": "",
            "RUT_impuesto": "",
            "Respon_fiscales": "",
            "Num_matricula_mercantil": "",
            "Nombre_contacto": "",
            "Tel_contacto": "",
            "Telfax_contacto": "",
            "Correo_contacto": "",
            "Nota_contacto": ""
        }
        QR = {
            "active": "enabled"
        }
        Periodo_pago = {
            "active": "disabled",
            "fecha_inicial": "",
            "fecha_final": ""
        }
        Metodo_pago = {
            "active": "enabled",
            "codigo_metodo": "1",
            "codigo_medio": str(journal.ei_payment_method) if journal.ei_payment_method else "10",
            "fecha_vencimiento": inv.date_due or inv.date_invoice,
            "identificacion_metodo": "Efectivo"
        }
        Referencia_factura = {
            "active": ncnd,
            "referencia_afectada": reference.number if ncnd == "enabled" else "",
            "cufe_cude": cude if ncnd == "enabled" else "",
            "algoritm_cufe_cude": "CUFE-SHA384",
            "fecha_factura": date_reference if ncnd == "enabled" else ""
        }
        Referencia_factura2 = {
            "active": "disabled",
            "referencia_afectada": "",
            "cufe_cude": "",
            "algoritm_cufe_cude": "",
            "fecha_factura": ""
        }
        respuesta_discrepancia = {
            "active": ncnd,
            "referencia": reference.number if ncnd == "enabled" else "",
            "codigo": "4" if tp == 'nc' else "6" if tp == "nd" else "",
            "descripci\u00f3n_correccion": ""
        }
        reference = getattr(inv, 'name', False)
        order_de_referencia = {
            "active": "enabled" if reference else "disabled",
            "codigo": str(inv.name.encode('utf-8')) if isinstance(inv.name, unicode) else "",
            "IssueDate": inv.date_invoice,
        }
        Referencia_envio = {
            "active": "disabled",
            "id": ""
        }
        Referencia_recibido = {
            "active": "disabled",
            "id": ""
        }
        Terminos_de_entrega = {
            "active": "disabled",
            "terminos_Especiales": "",
            "cod_respo_perdida": ""
        }
        currency_rate = "enabled" if inv.currency_id != company.currency_id else "disabled"
        Tasa_cambio = {
            "active": currency_rate,
            "Divisa_base": inv.currency_id.name,
            "Divisa_a_convertir": company.currency_id.name,
            "Valor": str(inv.tasa_manual or 1.0),
            "Fecha_conversion": inv.date_invoice
        }
        AdditionalDocumentReference = {
            "active": "disabled",
            "pre_consec": "",
            "fecha_creacion": "",
            "identificador": ""
        }
        Anticipos = [
            {
                "active": "disabled",
                "tipo_anticipo": "RED3123856",
                "valor_pago": "1000.00",
                "fecha_recibido": "2018-10-01",
                "fecha_realizado": "2018-09-29",
                "hora_realizado": "23:02:05",
                "instrucciones": "Prepago recibido"
            },
            {
                "active": "disabled",
                "tipo_anticipo": "RED3123857",
                "valor_pago": "850.00",
                "fecha_recibido": "2018-10-01",
                "fecha_realizado": "2018-09-29",
                "hora_realizado": "23:02:05",
                "instrucciones": "Prepago recibido"
            }
        ]
        Productos_servicios = []

        # Líneas de la factura
        for line in inv.invoice_line:
            # Items del documento
            sample = line.discount == 100.0
            line_taxes = [
                [
                    t.base_code_id.ei_code,
                    self.TAX_MAP[t.base_code_id.ei_code],
                    str(abs(round(t.amount * 100)))
                ] for t in
                line.invoice_line_tax_id if t.base_code_id.ei_code
                and 'auto' not in t.name.lower()
                and 'rte' not in t.name.lower()
                and 'rete' not in t.name.lower()
            ]
            taxes = reduce(lambda a, b: a + b, line_taxes or [0]) or []
            line_detail = {
                "active": "enabled",
                "Cantidad": str(line.quantity),
                "unidad_cantidad": str(line.uos_id.ei_uom_code),
                "Costo_unidad": str(round(line.price_unit, 2)),
                "Muestra": "Si" if sample else "No",
                "DeliveryLocation_active": "enabled" if line.product_id.default_code else "disabled",
                "DeliveryLocation_esq_id": "999",
                "DeliveryLocation_nombre": "",
                "DeliveryLocation_dato": line.product_id.default_code or "",
                "Codigo_muestra": "01" if sample else "0",
                "Desc_muestra": str(line.discount or 0.0),
                "Valor_muestra": str(round(line.price_unit, 2)) if sample else "0",
                "Descuento_cargo": "Credito",
                "ID_descuento_cargo": "11",
                "Porcentaje_descuento_cargo": "0.0" if sample else str(line.discount or 0.0),
                "Descripcion_descuento_cargo": "Otro descuento",
                "Mandatario": "",
                "Descripcion": line.product_id.name or "",
                "Prefijo_codigo_producto": "",
                "Codigo_producto": line.product_id.default_code or "",
                "Cantidad_x_paquete": "1",
                "Marca": "ninguna",
                "Modelo": "ninguna",
                "esquema_id": "",
                "esquema_dato": "",
                "esquema_name": "",
                "array_impuestos": taxes,
                "tributo_unidad": "0",
                "SellersItemIdentification_ID": "",
                "InformationContentProviderParty_ID": ""
            }

            Productos_servicios.append(line_detail)
            # DESCRIPCION DEL ITEM

        datafe = {
            "datos_conexion": datos_conexion,
            "tipo_documento": tipo_documento,
            "basicos_factura": basicos_factura,
            "respuesta": respuesta,
            "param_basico": param_basico,
            "facturador": facturador,
            "autorizacion_descarga": autorizacion_descarga,
            "WithholdingTaxTotal": WithholdingTaxTotal,
            "datos_empresa": datos_empresa,
            "datos_cliente": datos_cliente,
            "datos_transportadora": datos_transportadora,
            "QR": QR,
            "Periodo_pago": Periodo_pago,
            "Metodo_pago": Metodo_pago,
            "Referencia_factura": Referencia_factura,
            "Referencia_factura2": Referencia_factura2,
            "respuesta_discrepancia": respuesta_discrepancia,
            "order_de_referencia": order_de_referencia,
            "Referencia_envio": Referencia_envio,
            "Referencia_recibido": Referencia_recibido,
            "Terminos_de_entrega": Terminos_de_entrega,
            "Tasa_cambio": Tasa_cambio,
            "AdditionalDocumentReference": AdditionalDocumentReference,
            "Anticipos": Anticipos,
            "Productos_servicios": Productos_servicios
        }
        return datafe

    def send_invoice(self, inv):
        company = self.company_id
        datafe = self._get_invoice_json(inv)
        tp = ('ei' if (inv.type == 'out_invoice' and inv.journal_id.type == 'sale')
              else 'nc' if inv.type == 'out_refund' else 'nd')
        result = self.send_json(company.service_url, datafe, inv, tp)
        if result:
            inv.ei_cufe = result['cufe']
            inv.ei_cude = result['cude']
            inv.ei_qr = result['qr']
            response_64 = result['response_64']
            inv.ei_app_response = response_64
            inv.ei_state = 'dian_accep'
            dct = 'Factura Enviada con Exito'
            inv._create_ei_order_log(
                inv, inv.number, 'xml', tp, dct, response_64,
                'close', 'dian_accep'
            )
        else:
            inv.ei_state = 'dian_rejec'
        self.env.cr.commit()

    @api.multi
    def send_json(self, url, datafe, inv, tp):
        data = 'json_data=' + \
            base64.b64encode(json.dumps(datafe).encode('utf-8'))
        try:
            response = requests.post(
                url, data=data, headers=HEADERS, verify=False)
            dct = 'Factura Generada'
            self._create_ei_order_log(
                inv, inv.number, 'json', tp, dct,
                json.dumps(datafe).encode('utf-8'), 'open', 'done'
            )
            try:
                response_body = response.content
                _logger.info(response_body)
                valid = re.search(r'valid: \'(\w*)\'', response_body).group(1)
                cufe = re.search(r'cufe: \'(\w*)\'', response_body).group(1)\
                    if tp == 'ei' else ''
                cude = re.search(r'cufe: \'(\w*)\'', response_body).group(1)\
                    if tp != 'ei' else ''
                # num = re.search(r'num: \'(\w*)\'', response_body).group(1)
                qr = re.search(r'qr: \'(.*)\'', response_body).group(1)
                response_64 = re.search(
                    r'response_64: \'(.*)\'', response_body).group(1)
                response_xml = base64.b64decode(response_64)
                info_check = inv.number in response_xml.decode(
                    'utf-8') if inv.company_id.ei_server_type == 'production' else True
                _logger.info("Verificacion de informacion recibida: %s, %s" % (
                    inv.number, info_check))
                if not re.search('Documento validado por la DIAN', response_xml) or not info_check:
                    try:
                        response = re.search(
                            r'response: \'(.*)\'', response_body)
                        if response:
                            response_body = response.group(1)
                        else:
                            response_body = response.content
                    except:
                        response_body = 'No se encontro respuesta'
                    dct = 'La Factura fue rechazada'
                    self._create_ei_order_log(
                        inv, inv.number, 'xml', 'lg', dct, response_xml or response_body, 'open', 'dian_rejec'
                    )
                    return {}
                response_xml = base64.b64decode(response_64)
                inv._set_validation_date(response_xml)
                return {
                    'valid': valid,
                    'cufe': cufe,
                    'cude': cude,
                    'qr': qr,
                    'response_64': response_xml
                }
            except:
                dct = 'La Factura fue rechazada'
                error_log = re.search(
                    r'response_error: \'(.*)\'', response_body).group(1)
                msg = error_log if error_log else datafe
                self._create_ei_order_log(
                    inv, inv.number, 'json', 'lg', dct, msg, 'open', 'dian_rejec'
                )
                return {}
        except:
            dct = 'No fue posible enviar la factura al proovedor'
            self._create_ei_order_log(
                inv, inv.number, 'loghost', tp, dct, datafe, 'open', 'supplier_rejec'
            )
            return {}

    def _set_validation_date(self, xml_response):
        try:
            xml_issue_date = re.search(
                r'<cbc:IssueDate>(.*)</cbc:IssueDate>',
                xml_response).group(1)
            xml_issue_time = re.search(
                r'<cbc:IssueTime>(.*)</cbc:IssueTime>',
                xml_response).group(1)
            self.ei_validation_date = ' '.join(
                (xml_issue_date, xml_issue_time))
        except:
            utc_adj = '-05:00'
            self.ei_validation_date = str(
                datetime.strptime(self.create_date,
                                  "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))[11:] + utc_adj

    @api.multi
    def _check_file_size(self, name_file, att_doc):
        nf = name_file
        MAX_SIZE = 1999999
        try:
            os.chdir(self.company_id.ei_temporal_files or '/tmp')
        except (IOError, OSError, TypeError):
            raise Warning(u"Error en conexión a Ruta local de transferencia de FE '%s'. Revisar "
                          u"parametrización en Compañía o existencia de carpeta en el servidor local"
                          % self.company_id.ei_temporal_files)
        tmp_file = open(nf, 'w')
        tmp_file.write(att_doc.decode('base64'))
        tmp_file.close()
        if os.stat(nf).st_size > MAX_SIZE:
            os.remove(nf)
            raise Warning('El tamaño del archivo adjunto de Facturación Electrónica excede el máximo permitido, '
                          '2 Mb, por favor validar')
        os.remove(nf)

    electronic_invoice = fields.Boolean(
        'Factura Electronica', related='partner_id.electronic_invoice', readonly=True)
    ei_state = fields.Selection([('pending', 'No Transferido'), ('done', 'Emitido'), ('supplier_rejec', 'Rechazado PT'),
                                 ('supplier_accep', 'Aceptado PT'), ('dian_rejec',
                                                                     'Rechazado DIAN'),
                                 ('dian_accep', 'Aceptado DIAN'), ('ack_cus',
                                                                   'Recibido Cliente'),
                                 ('cus_rejec', 'Rechazado Cliente'), ('cus_accep', 'Aceptado Cliente')],
                                string='Estado FE', default='pending', readonly=True, copy=False,
                                help='Estado Factura Electrónica')
    ei_cufe = fields.Char('CUFE', help='Código Único de Factura Electrónica asignado por la DIAN', readonly=True,
                          size=96, track_visibility='onchange', copy=False)
    ei_cude = fields.Char('CUDE', help='Código Único de Notas asignado por la DIAN', readonly=True,
                          size=96, track_visibility='onchange', copy=False, oldname='ei_uuid')
    ei_qr = fields.Char(string='Informacion QR', readonly=True, copy=False)
    ei_qr_data = fields.Binary(compute='_get_qr_data')
    ei_order_log_ids = fields.One2many(
        'ei.order.log', 'invoice_id', string='Logs FE', readonly=True)
    contingency_invoice = fields.Boolean('Factura de Contingencia', help='Marque este check para indicar que la '
                                                                         'factura es de Contingencia')
    ci_transcription = fields.Char('Identificador Transcripción', size=15, help='Identificador de la transcripción '
                                   'de datos, asignado por el OFE; prefijo, consecutivo')
    ci_start_date = fields.Datetime('Inicio Contingencia')
    ci_end_date = fields.Datetime('Fin Contingencia')
    ci_identifier = fields.Char('Identificador Contingencia', help='Idenficador de la contingencia asignado a la '
                                'anotación hecha por el OFE en su bitacora de contigencias')
    customer_att = fields.Binary(
        'Adjuntos Cliente', help='Archivo adjunto de Facturación Electrónica', copy=False)
    cus_att_name = fields.Char('Nombre Adjunto Cliente', copy=False)
    pol_send_cus_att = fields.Boolean(
        'Política Envío Adj', related='company_id.send_cus_att', readonly=True)
    ei_xml_content = fields.Text(string='Contenido XML')
    ei_app_response = fields.Text(string='Contenido XML Application Response')
    ei_email_sent = fields.Boolean(string='Email Enviado')
    ei_validation_date = fields.Char(string='Hora de Validacion')

    @api.one
    def _get_qr_data(self):
        qr = qrcode.QRCode(
            version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=5, border=4, )
        # you can put here any attribute SKU in my case
        qr.add_data(self.ei_qr or '')
        qr.make(fit=True)
        img = qr.make_image()
        buffer = cStringIO.StringIO()
        img.save(buffer)
        img_str = base64.b64encode(buffer.getvalue())
        self.ei_qr_data = img_str

    @api.multi
    def write(self, vals):
        if 'customer_att' in vals and vals['customer_att']:
            self._check_file_size(vals['cus_att_name'], vals['customer_att'])
        return super(AccountInvoice, self).write(vals)

    @api.model
    def create(self, vals):
        if 'customer_att' in vals and vals['customer_att']:
            self._check_file_size(vals['cus_att_name'], vals['customer_att'])
        return super(AccountInvoice, self).create(vals)

    @api.multi
    def ei_write_folder(self):
        if self or self.company_id.ei_automatic_gen:
            self._gen_xml_invoice()
        return True

    @api.multi
    def action_cancel(self):
        if (self.company_id.electronic_invoice and self.type != 'in_invoice' and
                self.state in ['open', 'paid'] and self.ei_state != 'pending' and
                self.ei_order_log_ids and self.ei_state not in ['dian_rejec', 'supplier_rejec']):
            raise Warning(u'Esta Factura No Puede ser Cancelada, debido a que el tercero %s tiene activa la politica '
                          u'de Facturacion Electrónica y la Factura %s ya tiene generado el archivo XML de Factura '
                          u'Electrónica.' % (self.partner_id.name, self.number))
        return super(AccountInvoice, self).action_cancel()

    @api.multi
    def action_number(self):
        res = super(AccountInvoice, self).action_number()
        if (self.type not in ('in_invoice', 'in_refund')
                and self.company_id.xml_automatic_generation
                and self.journal_id.id_param):
            self.env.cr.commit()
            self.generate_electronic_invoice()
        return res

    @api.multi
    def ei_batch_generation(self):
        journals = self.env['account.journal'].search([
            ('id_param', '>', 0),
            ('type', 'in', ('sale', 'sale_add', 'sale_refund'))
        ])
        to_process_invoices = self.env['account.invoice'].search([
            ('ei_state', 'in', ('pending',)),
            ('state', 'in', ('open', 'paid')),
            ('journal_id', 'in', journals.ids)
        ], limit=160)
        self.env['ei.batch.process'].process_batch(to_process_invoices)


class AccountInvoiceRefund(models.TransientModel):
    _inherit = 'account.invoice.refund'

    @api.multi
    def invoice_refund(self):
        res = super(AccountInvoiceRefund, self).invoice_refund()
        inv_orig = self.env['account.invoice'].browse(
            self._context['active_id'])
        invoices = res['domain'][1][2]
        for inv in self.env['account.invoice'].browse(invoices):
            if hasattr(inv, 'n_oc') and inv_orig:
                inv.n_oc = getattr(inv_orig, 'n_oc', None)
        return res
