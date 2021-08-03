from celery import Celery
from threading import Thread
from datetime import datetime
from collections import OrderedDict
from http_helper import HEADERS
from http_helper import INVOICE
from http_helper import URL_XML
from http_helper import DEFAULT_SERVICE_URL
from db_helper import create_cursor
import os
import time
import base64
import json
# import requests
import grequests as requests
import qrcode
import re
import logging
_logger = logging.getLogger(__name__)

app = Celery('ei_mass_send', broker='amqp://localhost', backend='rpc://')
# backend='db+sqlite:///ei_tasks.db' backend='amqp'
GEVENT_SUPPORT = True


INVOICE = 0
NUMBER = 1
INVOICE_ID = 2
INV_TYPE_MAP = {
    "91": "nc",
    "92": "nd",
    "01": "ei",
    "00": "lg",
}

EI_ORDER_LOG_QUERY = """
insert into ei_order_log(
        name,
        transaction_date,
        name_file,
        type_log,
        type_doc,
        description,
        data,
        state,
        document_state,
        invoice_id
    )
values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""
EI_UPDATE_STATE_QUERY = """
update account_invoice set
    ei_state = %s,
    ei_cufe = %s,
    ei_cude = %s,
    ei_qr = %s
where id = %s;
"""
EI_UPDATE_VEREDICT_QUERY = """
update account_invoice set
    ei_state = %s
where id = %s;
"""
EI_UPDATE_XML_QUERY = """
update account_invoice set
    ei_xml_content = %s
where id = %s;
"""


def create_ei_order_log(cursor, ei_number, ei_id, type_log, type_doc,
                        description, data, state, document_state):
    query_data = OrderedDict([
        ('name', ei_number),
        ('transaction_date',
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ('name_file', ei_number),
        ('type_log', type_log),
        ('type_doc', type_doc),
        ('description', description),
        ('data', data),
        ('state', 'open'),
        ('document_state', 'done'),
        ('invoice_id', ei_id)
    ])
    try:
        cursor.execute(EI_ORDER_LOG_QUERY, tuple(query_data.values()))
        cursor.connection.commit()
    except:
        print('Error al crear log: %s' % ei_number)


def update_invoice_state(cursor, ei_id=0, data={}, veredict='pending'):
    ei_cufe = data.get('cufe', '')
    ei_cude = data.get('cude', '')
    ei_qr = data.get('qr', '')
    if data:
        try:
            cursor.execute(EI_UPDATE_STATE_QUERY,
                           (veredict, ei_cufe, ei_cude, ei_qr, ei_id))
            cursor.connection.commit()
            return
        except:
            print('Error al actualizar estado %s' % ei_id)
    try:
        cursor.execute(EI_UPDATE_VEREDICT_QUERY,
                       (veredict, ei_id))
        cursor.connection.commit()
    except:
        print('Error al actualizar estado %s' % ei_id)


def update_xml_content(cursor, ei_id=0, xml_fe=''):
    try:
        cursor.execute(EI_UPDATE_XML_QUERY,
                       (xml_fe, ei_id))
        cursor.connection.commit()
    except:
        print('Error al actualizar XML %s' % ei_id)


def get_invoice_info(ei_data):
    return {
        'type': INV_TYPE_MAP[
            ei_data.get('tipo_documento', {}).get('numero', '00')],
        'nit': ei_data.get('datos_conexion', {}).get('documento', '')
    }


def process_invoice_response(response, ei_data, ei_number, ei_id, invoice_info, cursor):
    json_data = json.dumps(ei_data).encode('utf-8')
    ei_type = invoice_info.get('type')
    try:
        print('Envio de factura: %s' % ei_number)
        create_ei_order_log(
            cursor, ei_number, ei_id, 'json', ei_type, 'Factura Generada',
            json_data, 'open', 'done'
        )
        try:
            print('Lectura de resultado: %s' % ei_number)
            response_body = response.content
            valid = re.search(r'valid: \'(\w*)\'', response_body).group(1)
            cufe = (re.search(r'cufe: \'(\w*)\'', response_body).group(1)
                    if ei_type == 'ei' else '')
            cude = (re.search(r'cufe: \'(\w*)\'', response_body).group(1)
                    if ei_type != 'ei' else '')
            qr = re.search(r'qr: \'(.*)\'', response_body).group(1)
            response_64 = re.search(
                r'response_64: \'(.*)\'', response_body).group(1)
            response_xml = base64.b64decode(response_64)
            info_check = ei_number.replace('-', '') in response_xml.decode('utf-8') or True
            print("Verificacion de informacion recibida: %s, %s" % (
                ei_number, info_check))
            if not re.search('Documento validado por la DIAN', response_xml) or not info_check:
                print('Rechazo en xml %s' % ei_number)
                try:
                    response = re.search(
                        r'response: \'(.*)\'', response_body)
                    if response:
                        response_body = response.group(1)
                    else:
                        response_body = response.content
                except:
                    response_body = 'No se encontro respuesta'
                create_ei_order_log(
                    cursor, ei_number, ei_id, 'xml', 'lg', 'La Factura fue rechazada',
                    response_xml or response_body, 'open', 'dian_rejec'
                )
                return {}
            return {
                'valid': valid,
                'cufe': cufe,
                'cude': cude,
                'qr': qr,
                'response_64': base64.b64decode(response_64)
            }
        except:
            print('rechazo en lectura de resultado %s' % ei_number)
            error_log = re.search(
                r'response_error: \'(.*)\'', response_body).group(1)
            create_ei_order_log(
                cursor, ei_number, ei_id, 'json', 'lg', 'La Factura fue rechazada',
                error_log if error_log else ei_data, 'open', 'dian_rejec'
            )
            return {}
    except:
        print('Rechazo pt %s' % ei_number)
        create_ei_order_log(
            cursor, ei_number, ei_id, 'loghost', 'lg',
            'La Factura fue rechazada',
            response.content or 'No se encontro respuesta',
            'open', 'supplier_rejec'
        )
        return {}


def process_invoice(ei_response, ei_data, ei_number, ei_id, cursor):
    invoice_info = get_invoice_info(ei_data)
    result = process_invoice_response(ei_response, ei_data, ei_number,
                                      ei_id, invoice_info, cursor)
    if result:
        update_invoice_state(cursor, ei_id, result, 'dian_accep')
        response_64 = result.get('response_64', '')
        create_ei_order_log(
            cursor, ei_number, ei_id, 'xml', invoice_info.get('type', 'lg'),
            'Factura Enviada con Exito', response_64,
            'close', 'dian_accep'
        )
        return True
    update_invoice_state(cursor, ei_id, {}, 'dian_rejec')
    return False


def get_xml_content(ei_response):
    try:
        xmlb64 = re.search(
            r'<b:XmlBytesBase64>(.*)</b:XmlBytesBase64>',
            ei_response.content).group(1)
        xml_fe = base64.b64decode(xmlb64)
        return xml_fe
    except:
        pass
    return ''


def process_xml_response(ei_response, ei_data, ei_number, ei_id, cursor):
    xml_fe = get_xml_content(ei_response)
    if not xml_fe:
        return False
    update_xml_content(cursor, ei_id, xml_fe)


def send_exception_handler(request, exception):
    print("Excepcion de envio")


@app.task
def send_invoice_batch(ei_batch, cursor_info):
    url = DEFAULT_SERVICE_URL
    ei_datas = [ei_info[INVOICE] for ei_info in ei_batch]
    json_datas = [json.dumps(ei_data).encode('utf-8') for ei_data in ei_datas]
    datas = ['json_data=' +
             base64.b64encode(json_data) for json_data in json_datas]
    with create_cursor(cursor_info) as cursor:
        results = requests.map(
            [requests.post(url, data=data, headers=HEADERS, verify=False)
             for data in datas],
            exception_handler=send_exception_handler
        )
        contents = ''
        for result, ei_info in zip(results, ei_batch):
            contents += result.content + '\n'
            process_invoice(result, ei_info[INVOICE], ei_info[NUMBER],
                            ei_info[INVOICE_ID], cursor)
    print('Batch Finished')


@app.task
def read_xml_batch(ei_batch, cursor_info):
    url = URL_XML
    ei_datas = [ei_info[INVOICE] for ei_info in ei_batch]
    json_datas = [json.dumps(ei_data).encode('utf-8') for ei_data in ei_datas]
    datas = ['json_data=' +
             base64.b64encode(json_data) for json_data in json_datas]
    with create_cursor(cursor_info) as cursor:
        results = requests.map(
            [requests.post(url, data=data, headers=HEADERS, verify=False)
             for data in datas],
            exception_handler=send_exception_handler
        )
        for result, ei_info in zip(results, ei_batch):
            process_xml_response(result, ei_info[INVOICE], ei_info[NUMBER],
                                 ei_info[INVOICE_ID], cursor)
    print('Batch Finished')
