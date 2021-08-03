import simplejson
import openerp
import openerp.http as http
from openerp.http import request
import openerp.addons.web.controllers.main as webmain
import json
import os


class AccountInvoiceAck(http.Controller):
    @http.route('/invoice/dian/accept', type='http', auth="public")
    def accept(self, db, token, id, **kwargs):
        registry = openerp.modules.registry.RegistryManager.get(db)
        invoice_pool = registry.get('account.invoice')
        state_change = None
        with registry.cursor() as cr:
            invoice_id = invoice_pool.search(cr, openerp.SUPERUSER_ID, [
                ('access_token', '=', token),
                ('ei_state', '!=', 'accepted'),
                ('id', '=', id)
            ])
            if invoice_id:
                state_change = invoice_pool.do_accept(
                    cr, openerp.SUPERUSER_ID, invoice_id)
        if not state_change:
            return
        return request.render('electronic_invoice.customer_accept_invoice', {})

    @http.route('/invoice/dian/reject', type='http', auth="public")
    def reject(self, db, token, id):
        registry = openerp.modules.registry.RegistryManager.get(db)
        invoice_pool = registry.get('account.invoice')
        state_change = None
        with registry.cursor() as cr:
            invoice_id = invoice_pool.search(cr, openerp.SUPERUSER_ID, [
                ('access_token', '=', token),
                ('ei_state', '!=', 'accepted'),
                ('id', '=', id)
            ])
            if invoice_id:
                state_change = invoice_pool.do_reject(
                    cr, openerp.SUPERUSER_ID, invoice_id)
        if not state_change:
            return
        return request.render('electronic_invoice.customer_reject_invoice', {})
