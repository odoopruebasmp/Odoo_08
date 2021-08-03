# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp import api
from openerp.exceptions import Warning

class mrp_product_produce_line(osv.osv_memory):
    _inherit="mrp.product.produce.line"

    _columns = {
        'move_id': fields.many2one('stock.move', 'Movimiento Asociado'),
        'string_availability_info': fields.char('Reserva', readonly=True),
    }

class mrp_product_produce(osv.osv_memory):
    _inherit="mrp.product.produce"

    def _get_product_qty(self, cr, uid, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid, context['active_id'], context=context)
        quantity = 0.0
        for move in prod.move_created_ids:
            if move.product_id == prod.product_id and move.state != 'draft':
                quantity += move.product_uom_qty
        return quantity

    def on_change_qty(self, cr, uid, ids, product_qty, consume_lines, context=None):
        # res = super(mrp_product_produce, self).on_change_qty(cr, uid, ids, product_qty, consume_lines, context=context)

        prod_obj = self.pool.get("mrp.production")
        uom_obj = self.pool.get("product.uom")
        move_obj = self.pool.get("stock.move")
        lot_obj = self.pool.get("stock.production.lot")
        production = prod_obj.browse(cr, uid, context['active_id'], context=context)
        consume_lines = []
        new_consume_lines = []
        if product_qty > 0.0:
            product_uom_qty = uom_obj._compute_qty(cr, uid, production.product_uom.id, product_qty, production.product_id.uom_id.id)
            consume_lines = prod_obj._calculate_qty(cr, uid, production, product_qty=product_uom_qty, context=context)
            sorted_lines=sorted(production.move_lines, key=lambda x: x.create_date)
            for line in consume_lines:
                if line['lot_id']:
                    lot = lot_obj.browse(cr, uid, line['lot_id'], context=context)
                    line.update({'string_availability_info':'['+lot.name+']'+'('+str(line['product_qty'])+')'})
                    # line.update({'string_availability_info':'['+lot.name+']'+'('+str(line['product_qty'])+')', 'move_id': move.id})

        for consume in consume_lines:
            new_consume_lines.append([0, False, consume])
        return {'value': {'consume_lines': new_consume_lines}}

    _defaults = {
         'product_qty': _get_product_qty,
    }

    def get_qty_available_per_product_per_location(self, line, production):
        location = (production.routing_id.location_id 
                    or production.location_src_id)
        moves = getattr(production, 'move_lines') or []
        move_pool = '(' + (','.join(str(move.id) for move in moves) or '-1')\
            + ')'
        self._cr.execute("""select sum(sq.qty) from
        stock_quant sq
        where (sq.reservation_id is null
        or sq.reservation_id in {0})
        and sq.product_id = {1}
        and sq.location_id = {2}""".format(
            move_pool, line.product_id.id, location.id
        ))
        qty_available = self._cr.fetchone()
        return (
            line.product_id.id,
            qty_available[0] if qty_available and qty_available[0] else 0.0,
            location.id
        )

    def get_qty_requested_per_product_per_location(self, production):
        location = (production.routing_id.location_id 
                    or production.location_src_id)
        return sorted([
            (line.product_id.id,
            sum(
                i.product_qty for i in self.consume_lines
                if i.product_id.id == line.product_id.id
            ),
            location.id)
            for line in self.consume_lines if line.product_id.type == 'product'
        ], key=lambda k_item: k_item[0])

    def validate_requested_vs_available(self, requested, available):
        prod, qty, loc = 0, 1, 2
        _available = filter(
            lambda av: requested[prod] == av[prod]\
                and requested[loc] == av[loc],
            available
        )
        available_qty = _available[0][qty] if _available else 0.0
        return requested[qty] > available_qty

    def _get_lot_unavailable(self, line, production):
        location = (production.routing_id.location_id 
                    or production.location_src_id)
        moves = getattr(production, 'move_lines') or []
        move_pool = '(' + (','.join(str(move.id) for move in moves) or '-1')\
            + ')'
        self._cr.execute("""select sum(sq.qty) from
        stock_quant sq
        where
        (sq.reservation_id is null
        or sq.reservation_id in {0})
        and sq.lot_id = {1}
        and sq.product_id = {2}
        and sq.location_id = {3}
        """.format(
            move_pool, line.lot_id.id or -1, line.product_id.id,
                location.id
        ))
        qty_available = self._cr.fetchone()
        lot_qty_available = qty_available[0] if qty_available\
            and qty_available[0] is not None else 0.0
        return line.product_qty > lot_qty_available

    @api.one
    def validate_quantities_to_transfer(self, production):
        location = (production.routing_id.location_id 
                    or production.location_src_id)
        qty_available_per_product_per_location = sorted([
            self.get_qty_available_per_product_per_location(line, production)
            for line in self.consume_lines if line.product_id.type == 'product'
        ], key=lambda k_item: k_item[0])
        qty_requested_per_product_per_location =\
            self.get_qty_requested_per_product_per_location(production)
        not_available = sorted(set(filter(
            lambda requested:
                self.validate_requested_vs_available(requested,
                qty_available_per_product_per_location),
            qty_requested_per_product_per_location
        )))
        if not_available:
            prod, loc = 0, 2
            separator = ','
            products = separator.join([
                self.env['product.product'].browse([pql[prod]]).name\
                for pql in not_available
            ])
            locations = separator.join([
                self.env['stock.location'].browse([pql[loc]]).display_name\
                for pql in not_available
            ])
            raise Warning('Esta intentando mover mayores cantidades de\
                los productos: %s a las disponibles en las ubicaciones: %s\
                ' % (products, locations))
        item_lot_not_available = filter(
            lambda line: (self._get_lot_unavailable(line, production)
                and line.product_id.type == 'product'
                and line.lot_id),
            self.consume_lines
        )
        if item_lot_not_available:
            separator = ','
            lots = separator.join([
                item.lot_id.name for item in item_lot_not_available
            ])
            products = separator.join([
                item.product_id.name for item in item_lot_not_available
            ])
            locations = separator.join([
                location.name
            ])
            raise Warning('Esta intentando mover mayores cantidades de\
                los productos: %s a las disponibles en los lotes: %s\
                el las ubicaciones : %s' % (products, lots, locations))

    def do_produce(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('mrp.production').browse(cr, uid, context['active_id'], context=context)
        self.validate_quantities_to_transfer(cr, uid, ids, prod, context=context)
        for data in self.browse(cr, uid, ids, context=context):
            if data.mode == 'consume_produce':
                for workcenter in prod.workcenter_lines:
                    if workcenter.state != 'done':
                        raise osv.except_osv(_('Error !'),_("Primero debe terminar la orden de  trabajo '%s'")%(workcenter.name))
                quantity = 0
                for move in prod.move_created_ids:
                    if move.product_id == prod.product_id and move.state != 'draft':
                        quantity += move.product_uom_qty
                # if data.product_qty > quantity:
                    # raise osv.except_osv(_('Error !'),_("La cantidad producida no puede ser mayor a la pendiente"))
            if data.product_qty <= 0:
                raise osv.except_osv(_('Error !'),_("La cantidad producida no puede ser menor o igual a 0"))

        res = super(mrp_product_produce, self).do_produce(cr, uid, ids, context=context)
        return res

#