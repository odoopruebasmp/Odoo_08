# -*- coding: utf-8 -*-
from openerp import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    electronic_invoice = fields.Boolean(
        'Factura Electrónica', help="Gestión de Factura Electrónica")
    ei_partner_address = fields.Selection([('default', 'Cliente'), ('invoice', 'Direccion Factura'),
                                           ('delivery', 'Direccion Entrega')], string='Direccion',
                                          default='default')
    ean_localizacion = fields.Char(string='Localizacion EAN')
    ei_email = fields.Char(string='Email factura electrónica')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ResPartner, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if not self.env.user.company_id.electronic_invoice and 'nica" invisible="1" modifiers="{&quot;invisible&' \
                                                                   'quot;: true}"' not in res['arch']:
                res['arch'] = res['arch'].replace('Electr&#243;nica"', 'Electr&#243;nica" invisible="1" modifiers='
                                                                       '"{&quot;invisible&quot;: true}" ')
        return res

    @api.model
    def create(self, vals):
        if vals.get('type', False) == 'delivery' and (len(vals.get('street', '')) > 100 or
                                                      len(vals.get('name', '')) > 100):
            nmn_len, str_len = len(vals['name']), len(vals['street'])
            msg = u'los campos Nombre y Dirección' if nmn_len > 100 and str_len > 100 else 'el campo Nombre' \
                if nmn_len > 100 else u'el campo Dirección'
            raise Warning(u"Por favor ajustar %s de la dirección de entrega:\n- %s.\n\n"
                          u"Su longitud no debe superar 100 caracteres." % (msg, vals.get('name', '')))
        res = super(ResPartner, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'street' in vals or 'name' in vals:
            partners = self.filtered(lambda x: x.type == 'delivery' and (
                len(x.street) > 100 or len(x.name) > 100))
            if partners:
                msg = 'las direcciones' if len(
                    partners) > 1 else u'la dirección'
                partners = '\n'.join('- %s' % p.name for p in partners)
                raise Warning(u"Por favor revisar los campos Nombre y Dirección de %s de entrega:\n%s\n\n "
                              u"Su longitud no debe superar 100 caracteres." % (msg, partners))
        return res
