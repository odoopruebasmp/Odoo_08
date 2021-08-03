# -*- coding: utf-8 -*-
import os
import re
import zipfile
from datetime import datetime, timedelta
import logging
from openerp import models, fields, api
from openerp import SUPERUSER_ID
from openerp.tools import config
from openerp.exceptions import Warning
from batch_process import batch_process
from collections import deque

_logger = logging.getLogger(__name__)


class EIBatchProcess(models.TransientModel):
    _name = 'ei.batch.process'

    journals_ids = fields.Many2many(
        comodel_name='account.journal',
        domain=[('id_param', '!=', 0)],
        string='Diarios')

    message = fields.Char(string='Facturas')

    def _get_invoices_to_process(self):
        return self.env['account.invoice'].search([
            ('journal_id', 'in', self.journals_ids.ids),
            ('state', 'in', ['open', 'paid']),
            ('ei_state', 'in', ['pending', 'dian_rejec']),
        ])

    @api.onchange('journals_ids')
    def onchange_journal_ids(self):
        invoices = self._get_invoices_to_process()
        self.message = "%s Facturas por enviar" % len(invoices)

    @api.multi
    def get_cursor_info(self):
        conn_string = self.env.cr._cnx._original_dsn
        conn_param_string = conn_string.split(' ')
        return dict(map(
            lambda param: tuple(param.split('=')), conn_param_string))

    @api.multi
    def get_batch_to_process(self, invoices, json=None):
        batch = deque([])
        if json == 'invoice':
            for inv in invoices:
                try:
                    inv_json = inv._get_invoice_json(inv)
                    batch.append([inv_json, inv.number, inv.id])
                except:
                    continue
        if json == 'xml':
            for inv in invoices:
                try:
                    inv_json = inv._get_xml_json(inv)
                    batch.append([inv_json, inv.number, inv.id])
                except:
                    continue
        return list(batch)

    @api.multi
    def do_process_batch(self):
        if not self.journals_ids:
            return
        self.env.cr.execute(
            """select id from account_invoice where ei_state = 'pending'
            and state in ('open', 'paid')
            and ei_state in  ('pending', 'dian_rejec')
            and journal_id in %s""",
            (tuple(self.journals_ids.ids),)
        )
        n_batches = int(max(len(self.env.cr.fetchall()), 160) / 160)
        for _ in range(n_batches):
            to_process_invoices = self.env['account.invoice'].search([
                ('ei_state', 'in', ('pending', 'dian_rejec')),
                ('state', 'in', ('open', 'paid')),

                ('journal_id', 'in', self.journals_ids.ids)
            ], limit=160)
            self.process_batch(to_process_invoices)

    def process_batch(self, invoices=False):
        invoices_to_process = invoices
        if not invoices_to_process:
            return
        cursor_info = self.get_cursor_info()
        to_process_list = self.get_batch_to_process(
            invoices_to_process, json='invoice')
        batch_process(
            to_process_list, cursor_info, task='send_invoice_batch')
        to_process_list = self.get_batch_to_process(
            invoices_to_process, json='xml')
        batch_process(
            to_process_list, cursor_info, task='read_xml_batch')
