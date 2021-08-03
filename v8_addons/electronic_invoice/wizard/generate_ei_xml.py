# -*- coding: utf-8 -*-
from openerp import models, fields, api


class XmlMassiveGeneration(models.TransientModel):
    _name = 'xml.massive.generation'

    @api.onchange('invoices')
    def populate_invoices(self):
        invoices = self.env['account.invoice'].browse(
            self._context['active_ids'])
        txt = ''
        for inv in invoices.filtered(lambda x: x.type != 'in_invoice'
                                     and x.state in ['open', 'paid']
                                     and x.ei_state in ('pending', 'dian_rejec')):
            inv_s = 'Abierta' if inv.state == 'open' else 'Pagada'
            txt += u'- {n}  -  {p}  -  {s} \n'.format(
                n=inv.number, p=inv.partner_id.name, s=inv_s)
        self.invoices = txt

    invoices = fields.Text('Facturas a procesar', readonly=True,
                           help="Facturas con Estado 'No Transferido'")

    @api.multi
    def massive_ei_generation(self):
        active_invoices = self.env['account.invoice'].browse(
            self._context['active_ids'])
        to_send_invoices = active_invoices.filtered(
            lambda inv: inv.type != 'in_invoice'
            and inv.state in ['open', 'done']
            and inv.ei_state in ('pending', 'dian_rejec'))
        if not to_send_invoices:
            return
        if self.env.user.company_id.invoice_batch_process:
            ei_batch_process = self.env['ei.batch.process']
            ei_batch_process.process_batch(to_send_invoices)
        else:
            for invoice in to_send_invoices:
                invoice.generate_electronic_invoice()
