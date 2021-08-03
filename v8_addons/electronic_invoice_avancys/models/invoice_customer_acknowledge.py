# -*- coding: utf-8 -*-
import os
import re
import zipfile
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import logging
from openerp import models, fields, api
from openerp import SUPERUSER_ID
from openerp.tools import config
from openerp.exceptions import Warning
from email.utils import parseaddr
from zipfile import ZipFile
from itertools import groupby
from http_helper import HEADERS
from http_helper import INVOICE
from http_helper import URL_XML
import base64
import json
import requests
import qrcode
import uuid
import xml_helper


UNSUPPORTED_PDF_FORMAT = """
Formato de pdf de factura electrónica no encontrado,
verifique la parametrizacion en la compañia.
"""

_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    access_token = fields.Char(string='Access token')

    def valid_email_address(self):
        regex = r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)'
        emails = self.partner_id.ei_email or self.partner_id.email or ''
        email_list = emails.split(';')
        return filter(
            lambda email: re.match(regex, email),
            map(lambda email: parseaddr(email)[1], email_list))

    def send_acknowlegement_email(self, force_send=False):
        email_pool = self.env['mail.mail']
        for inv in self:
            try:
                inv.create_token()
                if not self.valid_email_address():
                    inv._create_ei_order_log(
                        inv, inv.number, 'none', 'lg', 'No se pudo generar Email',
                        'No se encontró email valido en el cliente', 'open', 'done'
                    )
                    continue
                email = inv.prepare_email()
                if not email:
                    _logger.error('No se pudo generar email FE %s' %
                                  inv.number)
                    continue
                email_pool = email_pool + email
                inv._create_ei_order_log(
                    inv, inv.number, 'none', 'rn', 'Email de aceptación generado',
                    '', 'open', 'done'
                )
                inv.ei_email_sent = True
            except:
                _logger.error('Error al generar email FE %s' % inv.number)
        if force_send:

            email_pool.send()

    @api.multi
    def resend_acknowlegement_email(self):
        self.send_acknowlegement_email(force_send=True)

    def prepare_email(self):
        mail_pool = self.env['mail.mail']
        ctx = self._context.copy()
        ctx.update({
            'dbname': self._cr.dbname,
        })
        template = self.env.ref(
            'electronic_invoice_avancys.electronic_invoice_customer_acknowlegement')
        try:
            mail_id = template.with_context(ctx).send_mail(
                self.id, force_send=False)
        except:
            return mail_pool
        mail = mail_pool.browse(mail_id)
        attachment_ids = self.get_attachments()
        zipped_attachments = self._zip_attachments(attachment_ids)
        if attachment_ids:
            mail.write({'attachment_ids': [(6, 0, zipped_attachments.ids)]})
            return mail
        return mail_pool

    def _zip_attachments(self, attachments):
        filestore = os.path.join(
            config['data_dir'], 'filestore', self.env.cr.dbname, )
        xml_file, pdf_file, = self.number + '.xml', self.number + '.pdf'
        zip_file = self.number + '.zip'
        att_zip_file = 'anexos_' + zip_file
        invoice_attachments = attachments.filtered(
            lambda att: att.name in [xml_file, pdf_file])
        other_attachments = attachments.filtered(
            lambda att: att.name not in [xml_file, pdf_file])
        current_dir = os.getcwd()
        try:
            os.chdir(self.company_id.ei_temporal_files)
            if other_attachments:
                with ZipFile(att_zip_file, 'w') as zip_invoice:
                    for att in other_attachments:
                        zip_invoice.write(os.path.join(
                            filestore, att.store_fname), att.name)
            with ZipFile(zip_file, 'w') as zip_invoice:
                for att in invoice_attachments:
                    zip_invoice.write(os.path.join(
                        filestore, att.store_fname), att.name)
                if other_attachments:
                    zip_invoice.write(
                        att_zip_file, att_zip_file)
            zipped_attachment = self.env['ir.attachment'].sudo().create({
                'name': zip_file,
                'datas_fname': zip_file,
                'type': 'binary',
                'datas': base64.encodestring(open(zip_file, 'r').read()),
                'res_model': 'account.invoice',
                'res_id': self.id,
                'mimetype': 'application/zip'
            })
            map(os.remove, [zip_file] +
                ([att_zip_file] if other_attachments else[]))
            os.chdir(current_dir)
            return zipped_attachment
        except Exception as e:
            _logger.error(e)
            os.chdir(current_dir)
            return attachments

    @api.one
    def get_invoice_attachments(self):
        self.get_attachments()
        return True

    def get_attachments(self):
        company = self.company_id
        xml_file = self.number + '.xml'
        pdf_file = self.number + '.pdf'
        attachment_pool = self.env['ir.attachment']
        attachment_domain = [
            ('res_model', '=', 'account.invoice'),
            ('res_id', '=', self.id),
        ]
        attachment_ids = attachment_pool.search(attachment_domain)
        attachment_names = attachment_ids.mapped(lambda att: att.name)
        if xml_file not in attachment_names:
            if not self.create_xml_attachment():
                return False
        if pdf_file not in attachment_names:
            if not self.create_pdf_attachment():
                return False
        updated_attachment_ids = attachment_pool.search(
            attachment_domain)
        sale_order_attachments = (company.send_cus_po
                                  and self.get_sale_order_attachments()
                                  or attachment_pool)
        picking_attachments = (company.send_remission
                               and self.get_picking_attachments()
                               or attachment_pool)
        if company.send_cus_att:
            return (updated_attachment_ids + sale_order_attachments
                    + picking_attachments)
        xml_and_pdf_attachments = updated_attachment_ids.filtered(
            lambda att: att.name in (xml_file, pdf_file)
        )
        return (xml_and_pdf_attachments + sale_order_attachments
                + picking_attachments)

    def get_invoice_pdf(self, template_id):
        try:
            report = self.env.ref(template_id)
            report.report_type
        except:
            raise Warning(UNSUPPORTED_PDF_FORMAT)
        if 'qweb-pdf' == report.report_type:
            try:
                pdf = self.env['report'].sudo().get_pdf(
                    self, report.report_name)
                return pdf
            except:
                raise Warning(UNSUPPORTED_PDF_FORMAT)
        elif 'pdf' == report.report_type:
            try:
                report_pool = self.pool.get('ir.actions.report.xml')
                ctx = self._context.copy()
                ctx.update({
                    'active_id': self.id,
                    'active_ids': self.ids,
                    'active_model': 'account.invoice',
                    'params': {'action': report.id}
                })
                data = {'report_type': 'pdf'}
                (pdf, _) = report_pool.render_report(
                    self._cr, SUPERUSER_ID, self.ids,
                    report.name, data, context=ctx
                )
                return pdf
            except:
                raise Warning(UNSUPPORTED_PDF_FORMAT)
        else:
            raise Warning(UNSUPPORTED_PDF_FORMAT)

    def create_pdf_attachment(self):
        template_id = self.company_id.ei_pdf_template
        pdf = self.get_invoice_pdf(template_id)
        filename = self.number + '.pdf'
        return self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas_fname': filename,
            'type': 'binary',
            'datas': base64.encodestring(pdf),
            'res_model': 'account.invoice',
            'res_id': self.id,
            'mimetype': 'application/x-pdf'
        })

    def _get_xml_json(self, inv):
        company = self.company_id
        co_partner = company.partner_id
        return {
            "datos_conexion": {
                "token": company.software_code,
                "documento": co_partner.ref
            },
            "key": {
                "cufe": inv.ei_cufe if inv.journal_id.type == 'sale' else inv.ei_cude
            },
            "Datos_software": {
                "ambiente": ("1" if company.ei_server_type == 'production'
                             else "0")
            }
        }

    def create_xml_attachment(self):
        xml_fe = self.ei_xml_content or self.get_xml(self._get_xml_json(self))
        if not xml_fe:
            return False
        if not self.ei_xml_content:
            self.ei_xml_content = xml_fe
        filename = self.number + '.xml'
        xml_att_document = self.build_attached_document()
        xml_fe_normalized = (xml_att_document.encode('utf-8') if
                             isinstance(xml_att_document, unicode) else xml_att_document)
        data_attach = {
            'name': filename,
            'datas_fname': filename,
            'datas': base64.b64encode(xml_fe_normalized),
            'res_model': 'account.invoice',
            'res_id': self.id,
            'mimetype': 'application/' + 'xml',
            'file_type': 'application/' + 'xml',
            'type': 'binary'
        }
        return self.env['ir.attachment'].sudo().create(data_attach)

    def get_xml(self, datafe):
        data = 'json_data=' + \
            base64.b64encode(json.dumps(datafe))
        try:
            response = requests.post(
                URL_XML, data=data, headers=HEADERS, verify=False)
            xmlb64 = re.search(
                r'<b:XmlBytesBase64>(.*)</b:XmlBytesBase64>',
                response.content).group(1)
            xml_fe = base64.b64decode(xmlb64)
            return xml_fe
        except:
            pass
        return ''

    def create_token(self):
        self.access_token = uuid.uuid4().hex

    @api.multi
    def do_accept(self):
        if self.ei_state in ('cus_accep', 'cus_rejec'):
            return False
        self.ei_state = 'cus_accep'
        return True

    @api.multi
    def do_reject(self):
        if self.ei_state in ('cus_accep', 'cus_rejec'):
            return False
        self.ei_state = 'cus_rejec'
        return True

    def get_sale_order_attachments(self):
        sale_orders = self.get_sale_orders()
        attachments = sale_orders.mapped(
            lambda order: self.get_order_attachment(order))
        return attachments

    def get_sale_orders(self):
        return self.invoice_line.mapped(
            lambda iline: iline.stock_move_ids).mapped(
            lambda move: move.sale_line_id).mapped(
            lambda sline: sline.order_id)

    def get_order_attachment(self, order):
        attachment_pool = self.env['ir.attachment']
        if not order.customer_po:
            return attachment_pool
        filename = order.cus_po_name or 'OrdenDeCompra.pdf'
        existing_attachment = attachment_pool.search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', order.id),
            ('name', '=', filename),
        ])
        if existing_attachment:
            return existing_attachment
        data_attach = {
            'name': filename,
            'datas_fname': filename,
            'datas': order.customer_po,
            'res_model': 'sale.order',
            'res_id': order.id,
            'mimetype': 'application/' + 'pdf',
            'file_type': 'application/' + 'pdf',
            'type': 'binary'
        }
        return self.env['ir.attachment'].sudo().create(data_attach)

    def get_picking_attachments(self):
        pickings = self.get_pickings()
        attachments = pickings.mapped(
            lambda picking: self.get_picking_attachment(picking))
        return attachments

    def get_pickings(self):
        return self.invoice_line.mapped(
            lambda iline: iline.stock_move_ids).mapped(
            lambda move: move.picking_id)

    def get_picking_attachment(self, picking):
        attachment_pool = self.env['ir.attachment']
        return attachment_pool.search([
            ('res_model', '=', 'stock.picking'),
            ('res_id', '=', picking.id)
        ])

    @api.multi
    def ei_email_mass_send(self):
        to_email_invoices = self.env['account.invoice'].search([
            ('ei_state', '=', 'dian_accep'),
            ('ei_email_sent', '=', False)
        ], limit=100)
        to_email_invoices.send_acknowlegement_email()

    def build_attached_document(self):
        vals = {
            'header': {
                'tags': self._get_header_tags(),
                'attrs': {}
            },
            'sender': {
                'tags': self._get_sender_tags(),
                'attrs': self._get_sender_attrs()
            },
            'receiver': {
                'tags': self._get_receiver_tags(),
                'attrs': self._get_receiver_attrs()
            },
            'attachment': {
                'tags': self._get_attachment_tags(),
                'attrs': {}
            },
            'doc_line': {
                'tags': self._get_doc_line_tags(),
                'attrs': self._get_doc_line_attrs()
            }
        }
        return xml_helper.build_xml_attached_document(
            self.ei_xml_content, self.ei_app_response, vals)

    def _get_header_tags(self):
        company = self.company_id
        utc_adj = '-05:00'
        issue_datetime = str(datetime.strptime(
            self.create_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5)) + utc_adj
        return {
            'UBLVersionID': 'DIAN 2.1',
            'CustomizationID': 'Documentos adjuntos',
            'ProfileID': 'DIAN 2.1',
            'ProfileExecutionID': ("1" if company.ei_server_type == 'production' else "2"),
            'ID': uuid.uuid4().hex,
            'IssueDate': issue_datetime.split(' ')[0],
            'IssueTime': issue_datetime.split(' ')[1],
            'DocumentType': u'Contenedor de Factura Electrónica',
            'ParentDocumentID': str(self.number)
        }

    def _get_sender_tags(self):
        company = self.company_id
        return {
            'RegistrationName': company.name,
            'CompanyID': company.partner_id.ref,
            'TaxLevelCode': company.tributary_obligations or 'R-99-PN',
            'ID': '01',
            'Name': 'IVA'
        }

    def _get_sender_attrs(self):
        company = self.company_id
        return {
            'CompanyID': {
                'schemeAgencyID': "195",
                'schemeID': ("1" if company.ei_server_type == 'production' else "2"),
                'schemeName': company.partner_id.ref_type.ei_code
            },
            'TaxLevelCode': {
                'listName': "48"
            },
        }

    def _get_receiver_tags(self):
        return {
            'RegistrationName': self.partner_id.name,
            'CompanyID': self.partner_id.ref,
            'TaxLevelCode': 'R-99-PN',
            'ID': '01',
            'Name': 'IVA'
        }

    def _get_receiver_attrs(self):
        company = self.company_id
        return {
            'CompanyID': {
                'schemeAgencyID': "195",
                'schemeID': ("1" if company.ei_server_type == 'production' else "2"),
                'schemeName': self.partner_id.ref_type.ei_code
            },
            'TaxLevelCode': {
                'listName': "48"
            },
        }

    def _get_attachment_tags(self):
        return {
            'MimeCode': 'text/xml',
            'EncodingCode': 'UTF-8',
            'Description': 'ei_xml_content',
        }

    def _get_doc_line_tags(self):
        issue_date = str(datetime.strptime(
            self.create_date, "%Y-%m-%d %H:%M:%S") - timedelta(hours=5))
        validation_date, validation_time = (self.ei_validation_date.split(
            ' ') if self.ei_validation_date else ('', ''))
        return {
            'LineID': '1',
            'ID': self.number,
            'UUID': (self.ei_cufe or self.ei_cude),
            'IssueDate': issue_date[:10],
            'DocumentType': 'ApplicationResponse',
            'MimeCode': 'text/xml',
            'EncodingCode': 'UTF-8',
            'Description': 'ei_app_response',
            'ValidatorID': u'Unidad Especial Dirección de Impuestos y Aduanas Nacionales',
            'ValidationResultCode': u'02',
            'ValidationDate': str(validation_date),
            'ValidationTime': str(validation_time),
        }

    def _get_doc_line_attrs(self):
        return {
            'UUID': {
                'schemeName': "CUFE-SHA384"
            }
        }
