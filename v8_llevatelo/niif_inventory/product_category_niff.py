# -*- coding: utf-8 -*-
from openerp.osv import osv
from openerp.osv import fields as fields2
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import openerp.netsvc
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, DAILY
import time
from dateutil import relativedelta, parser
import openerp.tools
import openerp.addons.decimal_precision as dp
from openerp.tools.safe_eval import safe_eval as eval
from openerp import models, api, _, fields
from openerp import api
from openerp.exceptions import ValidationError


class product_product(models.Model):
    _inherit = "product.product"

    @api.one
    @api.depends('price_niif','costo_estimado_de_venta','valor_de_reposicion','tipo_producto_niff','costo_niif','qty_niif','amount_costo_end','costo_end')
    def _compute_valor_realizable(self):
        if self.tipo_producto_niff:
            valor = 0
            if self.tipo_producto_niff == 'materia_prima':
                valor = self.valor_de_reposicion
            elif self.tipo_producto_niff == 'producto_terminado':
                valor = self.price_niif-self.costo_estimado_de_venta
            elif self.tipo_producto_niff == 'semi_elaborado':
                valor = self.costo_end*self.amount_costo_end/100

            valor_diferencia = valor - self.costo_niif

            if valor_diferencia < 0.0:
                deterioro='aplica'
            else:
                deterioro='no_aplica'
                valor_diferencia = 0.0

            self.valor_neto_realizable = valor
            self.valor_diferencia=valor_diferencia
            self.valor_diferencia_total = valor_diferencia*self.qty_niif
            if self and self.id:
                self._cr.execute(''' UPDATE product_product SET deterioro=%s WHERE id=%s ''',(deterioro,self.id))


    costo_niif = fields.Float(string='Costo Referencia', digits=dp.get_precision('Account'))
    costo_total_niif = fields.Float(string='Costo Total', digits=dp.get_precision('Account'))
    qty_niif = fields.Float(string='Cantidad', digits=dp.get_precision('account'))
    date_qty_cost = fields.Datetime(string='Fecha Corte', readonly=True)
    date_qty_cost_update = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_qty_cost = fields.Many2one('res.users', string='Actualizado por', readonly=True)

    price_niif = fields.Float(string='Precio venta minimo', digits=dp.get_precision('Account'))
    date_price = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_price = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    costo_estimado_de_venta = fields.Float(string='Costo/gasto estimado de venta', digits=dp.get_precision('Account'))
    date_cost_estimado = fields.Datetime(string='Fecha Corte', readonly=True)
    user_cost_estimado = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    amount_costo_end = fields.Integer(string='Estado del producto (%)')
    costo_end = fields.Float(string='Valor Realizable Referencia', digits=dp.get_precision('Account'))
    product_costo_end = fields.Many2one('product.product', string='Producto de Referencia')
    date_cost_end = fields.Datetime(string='Fecha Corte', readonly=True)
    user_cost_end = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    valor_de_reposicion = fields.Float(string='Valor de reposicion', digits=dp.get_precision('Account'))
    date_reposicion = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_reposicion = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    valor_diferencia = fields.Float(string='Valor de Diferencia', compute='_compute_valor_realizable', digits=dp.get_precision('Account'), store=True)
    valor_diferencia_total = fields.Float(string='Valor de Diferencia Total', compute='_compute_valor_realizable', digits=dp.get_precision('Account'), store=True)
    valor_neto_realizable = fields.Float(string='Valor Neto Realizable', compute='_compute_valor_realizable', digits=dp.get_precision('Account'), store=True)

    tipo_producto_niff = fields.Selection([('materia_prima', 'Matera Prima'), ('producto_terminado', 'Producto Terminado'), ('semi_elaborado', 'Semi Elaborado')], string='Tipo Material')
    deterioro = fields.Selection([('aplica', 'Aplica'), ('no_aplica', 'No Aplica')], string='Deterioro')
    deterioros_ids = fields.One2many('account.move.line', 'deterioro_niff_id', string='Registros de Deterioro', readonly=True)


    @api.multi
    def write(self, vals):
        if vals.get('costo_niif',False):
            vals.update({'date_cost':fields.datetime.now(),'user_cost':self._uid})
        if vals.get('price_niif',False):
            vals.update({'date_price':fields.datetime.now(),'user_price':self._uid})
        if vals.get('costo_estimado_de_venta',False):
            vals.update({'date_cost_estimado':fields.datetime.now(),'user_cost_estimado':self._uid})
        if vals.get('valor_de_reposicion',False):
            vals.update({'date_reposicion':fields.datetime.now(),'user_reposicion':self._uid})
        if vals.get('amount_costo_end',False):
            if vals.get('amount_costo_end',False) <= 0.0:
                raise osv.except_osv(_('Error !'), _("No es posible tener un valor menor o igual a cero,por favor valide el estado del producto"))
            if vals.get('amount_costo_end',False) >= 100.0:
                raise osv.except_osv(_('Error !'), _("No es posible tener un valor mayor o igual a cien,por favor valide el estado del producto"))
            vals.update({'date_cost_end':fields.datetime.now(),'user_cost_end':self._uid})

        res = super(product_product, self).write(vals)
        return res


class product_template(models.Model):
    _inherit = "product.template"

    costo_niif = fields.Float(string='Costo Referencia', digits=dp.get_precision('Account'))
    costo_total_niif = fields.Float(string='Costo Total', digits=dp.get_precision('Account'))
    qty_niif = fields.Float(string='Cantidad', digits=dp.get_precision('account'))
    date_qty_cost = fields.Datetime(string='Fecha Corte', readonly=True)
    date_qty_cost_update = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_qty_cost = fields.Many2one('res.users', string='Actualizado por', readonly=True)

    price_niif = fields.Float(string='Precio venta minimo', digits=dp.get_precision('Account'))
    date_price = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_price = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    costo_estimado_de_venta = fields.Float(string='Costo/gasto estimado de venta', digits=dp.get_precision('Account'))
    date_cost_estimado = fields.Datetime(string='Fecha Corte', readonly=True)
    user_cost_estimado = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    amount_costo_end = fields.Integer(string='Estado del producto (%)')
    costo_end = fields.Float(string='Valor Realizable Referencia', digits=dp.get_precision('Account'))
    product_costo_end = fields.Many2one('product.product', string='Producto de Referencia')
    date_cost_end = fields.Datetime(string='Fecha Corte', readonly=True)
    user_cost_end = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    valor_de_reposicion = fields.Float(string='Valor de reposicion', digits=dp.get_precision('Account'))
    date_reposicion = fields.Datetime(string='Fecha Actualizacion', readonly=True)
    user_reposicion = fields.Many2one('res.users', string='Actualizado Por', readonly=True)

    valor_diferencia = fields.Float(string='Valor de Diferencia', digits=dp.get_precision('Account'), store=True)
    valor_diferencia_total = fields.Float(string='Valor de Diferencia Total', digits=dp.get_precision('Account'), store=True)
    valor_neto_realizable = fields.Float(string='Valor Neto Realizable', digits=dp.get_precision('Account'))

    tipo_producto_niff = fields.Selection([('materia_prima', 'Matera Prima'), ('producto_terminado', 'Producto Terminado'), ('semi_elaborado', 'Semi Elaborado')], string='Tipo Material')
    deterioro = fields.Selection([('aplica', 'Aplica'), ('no_aplica', 'No Aplica')], string='Deterioro')


class account_move_line(models.Model):
    _inherit = "account.move.line"

    deterioro_niff_id = fields.Many2one('product.product', string='Deterioro Inventario')


class product_category(models.Model):
    _inherit = "product.category"

    account_depreciacion_debit_id = fields.Many2one('account.account', company_dependent=True, string='Cuenta Gasto Deterioro', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')])
    account_depreciacion_credit_id = fields.Many2one('account.account', company_dependent=True, string='Cuenta Deterioro', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')])
    account_income_niif = fields.Many2one('account.account', company_dependent=True, string='Reconocimiento Ingreso', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')])
    analytic_inventory_deterioro_id = fields.Many2one('account.analytic.account', company_dependent=True, string='Cuenta Analitica Deterioro')


class res_partner(models.Model):
    _inherit = "res.partner"

    account_income_niif = fields.Many2one('account.account', company_dependent=True, string='Pendientes Facturar', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')], select=True)
    account_reserve_niif = fields.Many2one('account.account', company_dependent=True, string='Factura de Reserva', domain=[('niif','=',True),('type','<>','view'), ('type', '<>', 'closed')], select=True)


class stock_picking_type(models.Model):
    _inherit = "stock.picking.type"

    journal_income_id=fields.Many2one('account.journal', string="Diario Provision Ingresos NIIF", domain="[('niif','=', True)]")


class res_company(models.Model):
    _inherit = "res.company"

    niif_income = fields.Boolean(string='Reconocimiento Ingresos NIIF', help="POLITICA A NIVEL DE COMPANIA, AFECTACION EN EL PROCESO DE REMISION DE VENTA. El sistema realizara un apunte contable, en el cual reconoce el ingreso desde la remision, esto afecta una cuenta puente NIIF del ingreso contra una cuenta NIIF del activo.Esta configuracion tambien genera el movimiento inverso en la facturacion, de tal forma que deben quedar en ceros, los pedidos ya facturados.")
    account_tax_active_niif_id = fields.Many2one('account.account', company_dependent=True, string='Impuesto Diferido Activo', domain=[('type','<>','view'), ('type', '<>', 'closed')], select=True)
    account_tax_pasivo_niif_id = fields.Many2one('account.account', company_dependent=True, string='Impuesto Diferido Pasivo', domain=[('type','<>','view'), ('type', '<>', 'closed')], select=True)
    account_tax_expense_niif_id = fields.Many2one('account.account', company_dependent=True, string='Impuesto Gasto', domain=[('type','<>','view'), ('type', '<>', 'closed')], select=True)
    account_tax_income_niif_id = fields.Many2one('account.account', company_dependent=True, string='Impuesto Ingreso', domain=[('type','<>','view'), ('type', '<>', 'closed')], select=True)


class stock_picking(models.Model):
    _inherit = "stock.picking"

    move_income_niif = fields.Many2one('account.move', string='Reconocimiento Ingreso', readonly=True, copy=False)


    @api.cr_uid_ids_context
    def do_transfer(self, cr, uid, picking_ids, context=None):
        move_line_in = []
        if context is None:
            context = {}
        else:
            context = dict(context)

        move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        sequence_obj = self.pool.get('ir.sequence')
        tax_obj = self.pool.get('account.tax')
        period_obj = self.pool.get('account.period')
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        account_default_obj = self.pool.get('account.analytic.default')
        fabricante_id = False
        account_analytic_id=False

        for picking_to_validate in self.browse(cr, uid, picking_ids, context=context):

            # RESTRICCION DE DUPLICACION DE MOVIMIENTOS CONTABLES
            if not picking_to_validate.picking_type_id.journal_id:
                raise ValidationError("El sistema debe contar con un diario, configurado en el\
                    tipo de operacion %s"  % picking_to_validate.picking_type_id.name)

            picking_date = picking_to_validate.date_done and picking_to_validate.date_done[0:10] or datetime.now().date()
            period_id = period_obj.search(cr, uid, [('state','=','draft'),('date_start','<=',picking_date),('date_stop','>=',picking_date)], limit=1,context=context)
            if period_id:
                period_id = period_id[0]
            elif picking_to_validate.picking_type_id.code != "internal":
                raise ValidationError("El sistema debe contar con un periodo contable abierto para\
                    este tipo de transferencia para la fecha %s"  % picking_date)

            if not picking_to_validate.partner_id:
                raise ValidationError("El sistema debe contar con un tercero\
                    asociado al movimiento de inventario %s" % picking_to_validate.name)

            for picking_move in picking_to_validate.move_lines:
                user_owners = [uo.id for uo in picking_move.location_dest_id.user_owners_ids]
                if uid not in user_owners and len(picking_move.location_dest_id.user_owners_ids) >= 1:
                    raise ValidationError("No tiene autorizacion para realizar este movimiento.\
                        Usted no es responsable de las entradas de para\
                        la ubicacion '%s'" % picking_move.location_dest_id.name)
                user_owners = [uo.id for uo in picking_move.location_id.user_owners_ids]
                if uid not in user_owners and len(picking_move.location_id.user_owners_ids) >= 1:
                    raise ValidationError("No tiene autorizacion para realizar este movimiento.\
                        Usted no es responsable de las salidas de para\
                        la ubicacion '%s'" % picking_move.location_id.name)
                if picking_move.location_id.usage == "view" or picking_move.location_dest_id.usage == "view":
                        raise ValidationError("El sistema no permite realizar movimientos desde/para una  ubicacion de tipo VISTA, por favor valide el origen y destino del movimeinto de inventario")

                move = picking_move
                pick = picking_to_validate
                product_data = move.product_id
                product_qty = move.product_qty
                price_unit = move.price_unit
                cost = move.cost
                asset = False
                partner_id = pick.partner_id
                if (move.location_id.usage != "internal" or move.location_dest_id.usage != "internal") and move.product_id.type == "product" and move.state != "cancel" and not asset:
                    if move.location_id.usage == "supplier" and move.location_dest_id.usage == "internal":#COMPRAS
                        if pick.picking_type_id.code != "incoming":
                            raise ValidationError("El sistema no puede transferir un movimiento de\
                                inventario que no esta alineado a su tipo de operacion, por favor validar\
                                el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento.")
                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise ValidationError("El sistema debe contar con una cuenta de entrada de almacen.\
                                Esta se debe configurar en el producto '%s' en la sesion de contabilidad\
                                o en la categoria '%s'."  % (product_data.name, product_data.categ_id.name))
                        tax_mayor_valor = []
                        impuestos_mayor_valor = {}
                        if self.pool.get('ir.module.module').search(cr, uid, [('name','=','stock_picking_dotacion'),
                                                                                ('state','=','installed')], context=context):
                            refund = move.picking_id.is_refund
                        if move.purchase_line_id:
                            for tax_check in move.purchase_line_id.taxes_id:
                                if tax_check.mayor_valor:
                                    tax_mayor_valor.append(tax_check)
                            if len(tax_mayor_valor) > 1:
                                raise ValidationError("Hay mas de un impuesto de mayor valor para el producto '%s'" % (move.product_id.name))
                        else:
                            move_origin = move_obj.search(cr, uid, [('picking_id','=',move.picking_id.id),('id','!=',move.id),('product_id','=',move.product_id.id),('purchase_line_id','!=',False)], context=context)
                            if move_origin:
                                pass
                            else:
                                if not refund:
                                    raise ValidationError("El producto '%s' con referencia interna '%s' no esta asociado a la orden de compra '%s'. Si desea incluirlo en la recepcion debe 1.Cancelar O.C. ---->   2.Regresar a borrador ---->   3.Modificar la O.C. ---->   4.Confirmar O.C." % (move.product_id.name, move.product_id.default_code, pick.origin))

                        if tax_mayor_valor:
                            additional_cost = (cost*product_qty) - (price_unit*product_qty + impuestos_mayor_valor['amount'])

                            if not currency_obj.is_zero(cr, uid, move.local_currency_id, additional_cost):
                                if additional_cost < -1 and not refund:
                                    raise ValidationError("El costo del producto '%s' no puede ser menor al valor configurado, el costo es '%s' mientras el precio es '%s'"  % (n, cost, price_unit))
                                if additional_cost > 0:
                                    transit_account = (product_data.transit_accout_id and product_data.transit_accout_id.id) or (product_data.categ_id.transit_accout_id and product_data.categ_id.transit_accout_id.id) or False
                                    if not transit_account:
                                        raise ValidationError("La cuenta de transito no esta definida en el producto '%s' ni en su categoria"  % product_data.name)

                    elif move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and pick.picking_type_id.code != "return":#DEVOLUCION VENTAS 1
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        if pick.picking_type_id.code != "incoming":
                            raise ValidationError("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion,\
                                por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento.")

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise ValidationError("El sistema debe contar con una cuenta de entrada de almacen.\
                                Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % (product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return:
                            raise ValidationError("El sistema debe contar con una cuenta de costo de venta.\
                                Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % (product_data.name, product_data.categ_id.name))

                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            account_analytic_id = move.origin_returned_move_id and move.origin_returned_move_id.account_analytic_id and move.origin_returned_move_id.account_analytic_id.id

                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                    cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                else:
                                    raise ValidationError("El sistema esta configurado para requerir la cuenta analitica en el\
                                        proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''.\
                                        Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA'\
                                        o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code)

                    elif move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and pick.picking_type_id.code == "return":#DEVOLUCION VENTAS 2
                        if pick.picking_type_id.code != "return":
                            raise ValidationError("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion,\
                                por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento.")

                        id_s = []
                        date_dev=pick.date_dev or pick.date
                        cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True and date_start <= %s and date_end >= %s ) and product_id=%s',(partner_id.property_product_pricelist.id,date_dev,date_dev,product_data.id))
                        result = cr.fetchone()
                        if not result:
                            cr.execute('SELECT id  FROM product_pricelist_item where price_version_id in (SELECT  id FROM product_pricelist_version where pricelist_id=%s and active=True) and product_id=%s',(partner_id.property_product_pricelist.id,product_data.id))
                            result = cr.fetchone()
                            if result:
                                id_s = result[0]
                        else:
                            id_s = result[0]

                        if not id_s:
                            if pick.company_id.sale_cost_invoice:
                                raise ValidationError("el producto '%s' no esta definido en la lista de precios "  % product_data.name)
                            else:
                                price = product_data.lst_price

                        account_debit_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ and product_data.categ_id.property_stock_account_input_categ.id

                        account_credit_id = product_data.cogs_account_id and product_data.cogs_account_id.id or product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id

                        if not account_debit_id:
                            raise ValidationError("La cuenta de entrada de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name)

                        if not account_credit_id:
                            raise ValidationError("La cuenta de devolucion no esta definida en el producto '%s' ni en su categoria"  % product_data.name)

                    elif move.location_id.usage != "internal" and move.location_dest_id.usage == "internal":#AJUSTES/PRODUCCIONES/OTROS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            continue

                        if pick.picking_type_id.code not in ["incoming", "return"]:
                            raise ValidationError("El sistema no puede transferir un movimiento de inventario que no esta alineado a su tipo de operacion,\
                                por favor valir el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento.")

                        account_id = product_data.property_stock_account_input and product_data.property_stock_account_input.id or product_data.categ_id.property_stock_account_input_categ.id
                        if not account_id:
                            raise ValidationError("El sistema debe contar con una cuenta de entrada de almacen.\
                                Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % (product_data.name, product_data.categ_id.name))

                        account_move_return = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                        if not account_move_return and not move.origin_returned_move_id:
                            raise ValidationError("El sistema debe contar con una cuenta de costo de venta.\
                                Esta, se debe configurar en el producto '%s' en la sesion de contabilidad o en la categoria '%s'."  % (product_data.name, product_data.categ_id.name))


                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "customer":#VENTAS
                        if pick.company_id and pick.company_id.sale_cost_invoice:
                            price = product_data.standard_price
                            price_total = price*product_qty
                            # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                            if price <= 0.0 and pick.company_id.restriction_cost_zero:
                                raise ValidationError("El movimiento que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada.")
                            continue

                        if pick.picking_type_id.code == "customer":
                            raise ValidationError("El sistema no puede transferir un movimiento de inventario\
                                que no esta alineado a su tipo de operacion, por favor valir el tipo de\
                                operacion que quiere realizar y la ubicacion origen y destino del movimiento.")

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise ValidationError("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name)

                        # Contabilidad Analitica por default
                        if pick.company_id.analytic_default:
                            sale_order_line = move.sale_line_id
                            account_analytic_id = (sale_order_line.account_analytic_id.id
                                if getattr(sale_order_line, 'account_analytic_id', False) else False)\
                                    or getattr(sale_order_line.order_id.project_id, 'id') if sale_order_line else False
                            if not account_analytic_id:
                                analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                if analytic_id:
                                    pass
                                else:
                                    raise ValidationError("El sistema esta configurado para requerir\
                                        la cuenta analitica en el proceso de remision, sin embargo no logra encontrar\
                                        una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene\
                                        valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta\
                                        fue generado por un usuario que no es comercial." % move.product_id.default_code)
                        else:
                            if 'is_dotation' in self._fields:
                                if pick.is_dotation or pick.to_puesto:
                                    if not pick.analytic_account_id:
                                        raise Warning("No se ha definido una cuenta analitica en la asignacion de dotacion")
                                    else:
                                        account_analytic_id = pick.analytic_account_id.id
                            else:
                                pass

                        account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or \
                                        (product_data.categ_id.cogs_account_id and
                                        product_data.categ_id.cogs_account_id.id) or False

                        if not account_id:
                            raise ValidationError(
                                "La cuenta de Costos de Venta no esta configurada en el producto %s ni en su\
                                categoria" % move.product_id.default_code)

                        if move.product_id.valuation == 'real_time':
                            raise ValidationError("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado"  % product_data.name)

                        # Flujo de ventas SCB
                        if getattr(pick, 'sale_stock_picking', None):
                            account_id = product_data.categ_id.account_production_transit_id and product_data.categ_id.account_production_transit_id.id or False
                            if not account_id:
                                raise ValidationError("Debe configurar la cuenta de producto en proceso de la categoria\
                                    '%s' para realizar el reconocimiento de producto donde el cliente"  % product_data.categ_id.name)


                    elif move.location_id.usage == "internal" and move.location_dest_id.usage == "supplier":#DEVOLUCION COMPRAS
                        if pick.picking_type_id.code == "customer":
                            raise ValidationError("El sistema no puede transferir un movimiento de inventario\
                                que no esta alineado a su tipo de operacion, por favor valir el tipo de operacion\
                                que quiere realizar y la ubicacion origen y destino del movimiento.")


                        if not partner_id.accrued_account_payable_id:
                            raise ValidationError("El sistema debe contar con la parametrizacion de la cuenta puente de recepcion del tercero '%s', se sugiere una cuenta del pasivo 26."  % partner_id.name)

                        output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                        if not output_account_id:
                            raise ValidationError("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name)


                    elif move.location_id.usage == "internal" and move.location_dest_id.usage != "internal":#AJUSTES/PRODUCCIONES/OTROS
                            if pick.company_id and pick.company_id.sale_cost_invoice:
                                price = product_data.standard_price
                                price_total = price*product_qty
                                # RESTRICCION DE MOVIMIENTOS CON COSTO CERO
                                if price <= 0.0 and pick.company_id.restriction_cost_zero:
                                    raise ValidationError("El movimiento que esta tratando de transferir tiene un costo menor o igual a cero, por favor valide con el area encargada.")
                                continue

                            if pick.picking_type_id.code == "customer":
                                raise ValidationError("El sistema no puede transferir un movimiento de \
                                    inventario que no esta alineado a su tipo de operacion, por favor valir\
                                    el tipo de operacion que quiere realizar y la ubicacion origen y destino del movimiento.")

                            output_account_id = product_data.property_stock_account_output and product_data.property_stock_account_output.id or product_data.categ_id.property_stock_account_output_categ.id
                            if not output_account_id:
                                raise ValidationError("La cuenta de salida de almacen no esta definida en el producto '%s' ni en su categoria"  % product_data.name)

                            if move.product_id.valuation == 'real_time':
                                raise ValidationError("Cambiar configuracion de evaluacion del producto '%s', modo tiempo real no soportado"  % product_data.name)

                            account_id = (product_data.cogs_account_id and product_data.cogs_account_id.id) or (product_data.categ_id.cogs_account_id and product_data.categ_id.cogs_account_id.id) or False
                            if not account_id:
                                raise ValidationError("La cuenta de costo de venta no esta definida en el producto '%s' ni en su categoria"  % product_data.name)


        res = super(stock_picking, self).do_transfer(cr, uid, picking_ids, context=context)
        otros='otros'

        for pick in self.browse(cr, uid, picking_ids, context=context):
            if pick.move_lines[0].location_id.usage == 'customer' or pick.move_lines[0].location_dest_id.usage == 'customer':
                if pick.picking_type_id.code == "outgoing":
                    if pick.move_income_niif:
                        raise osv.except_osv(_('Error !'), _("POR FAVOR ACTUALICE Y VALIDE EL ESTADO DE LA TRANSFERENCIA"))
                    if pick.company_id.niif_income:
                        company_id = pick.company_id.id

                        picking_date = pick.date_done or datetime.now().date()

                        # Validacion del tercero
                        if pick.partner_id and pick.partner_id.parent_id:
                            partner_id = pick.partner_id.parent_id
                        elif pick.partner_id:
                            partner_id =pick.partner_id
                        else:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un tercero asociado al movimiento de inventario %s" % pick.name))

                        # Validacion del Diario
                        journal_id = pick.picking_type_id.journal_income_id or False
                        if not journal_id:
                            raise osv.except_osv(_('Configuration !'), _("La operacion '%s', debe contar con un diario de Provision de Ingresos niif configurado."  % pick.picking_type_id.name))

                        # Validacion del periodo
                        period_id = period_obj.search(cr, uid, [('state','=','draft'),('date_start','<=',picking_date),('date_stop','>=',picking_date)], limit=1,context=context)
                        if period_id:
                            period_id = period_id[0]
                        elif pick.picking_type_id.code != "internal":
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un periodo contable abierto para este tipo de transferencia para la fecha %s"  % picking_date))

                        for move in pick.move_lines:
                            product_data = move.product_id
                            product_qty = move.product_qty
                            price_unit = move.price_unit
                            cost = move.cost
                            asset = False
                            try:
                                asset = product_data.is_asset
                            except:
                                asset = False

                            if move.location_id.usage == "internal" and move.location_dest_id.usage == "customer" and not asset and product_data.type == 'product':#VENTAS
                                sale_id = self.pool.get('sale.order').search(cr, uid, [('name', '=', pick.origin)], context=context)
                                if not sale_id:
                                    raise osv.except_osv(_('Error !'), _("No se encuentra un pedido con referencia '%s'."  % pick.origin))

                                sale_id = self.pool.get('sale.order').browse(cr, uid, sale_id, context=context)

                                if sale_id.order_policy == 'prepaid':
                                    output_account_id = partner_id.account_reserve_niif and partner_id.account_reserve_niif.id or False
                                    if not output_account_id:
                                        raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de factura de reserva en el cliente (28...) '%s'."  % partner_id.name))
                                else:
                                    output_account_id = partner_id.account_income_niif and partner_id.account_income_niif.id or False
                                    if not output_account_id:
                                        raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de provision de ingresos en el cliente (13...)  '%s'."  % partner_id.name))

                                # Contabilidad Analitica por default
                                if pick.company_id.analytic_default:
                                    sale_order_line = move.sale_line_id
                                    account_analytic_id = (sale_order_line.account_analytic_id.id
                                        if getattr(sale_order_line, 'account_analytic_id', False) else False)\
                                            or getattr(sale_order_line.order_id.project_id, 'id') if sale_order_line else False

                                    if not account_analytic_id:
                                        analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                        if analytic_id:
                                            account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                            cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                        else:
                                            raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))
                                else:
                                    account_analytic_id = move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False

                                account_id = product_data.categ_id.account_income_niif and product_data.categ_id.account_income_niif.id or False
                                if not account_id:
                                    raise osv.except_osv(_('Configuration !'), _("DEbe configurar la cuenta de provision de ingresos niif en la categoria '%s'"  % product_data.categ_id.name))


                                # PRECIO DE VENTA
                                price = move.price_unit
                                price_total = price*product_qty

                                cr_move_val = {
                                    'company_id': company_id,
                                    'journal_id': journal_id.id,
                                    'name': product_data.default_code or product_data.name,
                                    'ref': product_data.name,
                                    'ref1': product_data.name,
                                    'period_id': period_id,
                                    'account_id': account_id,
                                    'account_niif_id': account_id,
                                    'partner_id': partner_id.id,
                                    'analytic_account_id': account_analytic_id or False,
                                    'debit': 0.0,
                                    'credit': price_total,
                                    'date': picking_date,
                                    'tax_code_id': False,
                                    'base_code_id': False,
                                }
                                dr_move_val = cr_move_val.copy()
                                dr_move_val.update({
                                    'account_id': output_account_id,
                                    'account_niif_id': output_account_id,
                                    'credit': 0.0,
                                    'debit': price_total,
                                    'analytic_account_id': account_analytic_id or False,
                                })
                                move_line_in.append(dr_move_val)
                                move_line_in.append(cr_move_val)


                        move_id = False

                        if move_line_in:
                            move = {
                                'line_id': [],
                                'journal_id': journal_id.id,
                                'date': picking_date,
                                'period_id': period_id,
                            }
                            move_id = account_move_obj.create(cr, uid, move, context=context)
                            cr.execute(''' UPDATE stock_picking SET  move_income_niif = %s WHERE id = %s''',(move_id, pick.id))
                            for x in move_line_in:
                                cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, account_niif_id, analytic_account_id, partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id, company_id, journal_id.id, x['name'], period_id, x['account_id'], x['account_niif_id'], x['analytic_account_id'] or None, partner_id.id, float(x['debit']), float(x['credit']), x['date'], 'valid'))
                            account_move_obj.post(cr, uid, [move_id])

                if pick.picking_type_id.code == "incoming":
                    if pick.move_income_niif:
                        raise osv.except_osv(_('Error !'), _("POR FAVOR ACTUALICE Y VALIDE EL ESTADO DE LA TRANSFERENCIA"))
                    if pick.company_id.niif_income:
                        company_id = pick.company_id.id

                        picking_date = pick.date_done or datetime.now().date()

                        # Validacion del tercero
                        if pick.partner_id and pick.partner_id.parent_id:
                            partner_id = pick.partner_id.parent_id
                        elif pick.partner_id:
                            partner_id =pick.partner_id
                        else:
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un tercero asociado al movimiento de inventario %s" % pick.name))

                        # Validacion del Diario
                        journal_id = pick.picking_type_id.journal_income_id or False
                        if not journal_id:
                            raise osv.except_osv(_('Configuration !'), _("La operacion '%s', debe contar con un diario de Provision de Ingresos niif configurado."  % pick.picking_type_id.name))

                        # Validacion del periodo
                        period_id = period_obj.search(cr, uid, [('state','=','draft'),('date_start','<=',picking_date),('date_stop','>=',picking_date)], limit=1,context=context)
                        if period_id:
                            period_id = period_id[0]
                        elif pick.picking_type_id.code != "internal":
                            raise osv.except_osv(_('Configuration !'), _("El sistema debe contar con un periodo contable abierto para este tipo de transferencia para la fecha %s"  % picking_date))

                        for move in pick.move_lines:
                            product_data = move.product_id
                            product_qty = move.product_qty
                            price_unit = move.price_unit
                            cost = move.cost
                            asset = False
                            try:
                                asset = product_data.is_asset
                            except:
                                asset = False

                            if move.location_id.usage == "customer" and move.location_dest_id.usage == "internal" and not asset:#VENTAS

                                output_account_id = partner_id.account_income_niif and partner_id.account_income_niif.id or False
                                if not output_account_id:
                                    raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de provision de ingresos en el cliente '%s'."  % partner_id.name))

                                # Contabilidad Analitica por default
                                if pick.company_id.analytic_default:
                                    sale_order_line = move.sale_line_id
                                    account_analytic_id = (sale_order_line.account_analytic_id.id
                                        if getattr(sale_order_line, 'account_analytic_id', False) else False)\
                                            or getattr(sale_order_line.order_id.project_id, 'id') if sale_order_line else False

                                    if not account_analytic_id:
                                        analytic_id = account_default_obj.search(cr, uid, [('product_id', '=', move.product_id.id),('user_id', '=', pick.create_uid and pick.create_uid.id or False)], context=context, limit=1)
                                        if analytic_id:
                                            account_analytic_id=account_default_obj.browse(cr, uid, analytic_id[0], context=context).analytic_id.id
                                            cr.execute(''' UPDATE stock_move SET account_analytic_id=%s WHERE id=%s''',(account_analytic_id, move.id))
                                        else:
                                            raise osv.except_osv(_('Configuration !'), _("El sistema esta configurado para requerir la cuenta analitica en el proceso de remision, sin embargo no logra encontrar una cuenta para el producto '%s' y el usuario ''. Esto puede ser porque no tiene valores predeterminados 'CONSULTAR CON EL AREA ENCARGADA' o porque el pedido de venta fue generado por un usuario que no es comercial." % move.product_id.default_code, pick.create_uid.name))
                                else:
                                    account_analytic_id = move.account_analytic_id and move.account_analytic_id.id or account_analytic_id or False

                                account_id = product_data.categ_id.account_income_niif and product_data.categ_id.account_income_niif.id or False
                                if not account_id:
                                    raise osv.except_osv(_('Configuration !'), _("DEbe configurar la cuenta de provision de ingresos niif en la categoria '%s'"  % product_data.categ_id.name))


                                # PRECIO DE VENTA
                                price = move.price_unit
                                price_total = price*product_qty

                                cr_move_val = {
                                    'company_id': company_id,
                                    'journal_id': journal_id.id,
                                    'name': product_data.default_code or product_data.name,
                                    'ref': product_data.name,
                                    'ref1': product_data.name,
                                    'period_id': period_id,
                                    'account_id': output_account_id,
                                    'account_niif_id': output_account_id,
                                    'partner_id': partner_id.id,
                                    'analytic_account_id': account_analytic_id or False,
                                    'debit': 0.0,
                                    'credit': price_total,
                                    'date': picking_date,
                                    'tax_code_id': False,
                                    'base_code_id': False,
                                }
                                dr_move_val = cr_move_val.copy()
                                dr_move_val.update({
                                    'account_id': account_id,
                                    'account_niif_id': account_id,
                                    'credit': 0.0,
                                    'debit': price_total,
                                    'analytic_account_id': account_analytic_id or False,
                                })
                                move_line_in.append(dr_move_val)
                                move_line_in.append(cr_move_val)


                        move_id = False

                        if move_line_in:
                            move = {
                                'line_id': [],
                                'journal_id': journal_id.id,
                                'date': picking_date,
                                'period_id': period_id,
                            }
                            move_id = account_move_obj.create(cr, uid, move, context=context)
                            cr.execute(''' UPDATE stock_picking SET  move_income_niif = %s WHERE id = %s''',(move_id, pick.id))
                            for x in move_line_in:
                                cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, account_niif_id, analytic_account_id, partner_id, debit, credit, date, state) VALUES
                                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id, company_id, journal_id.id, x['name'], period_id, x['account_id'], x['account_niif_id'], x['analytic_account_id'] or None, partner_id.id, float(x['debit']), float(x['credit']), x['date'], 'valid'))
                            account_move_obj.post(cr, uid, [move_id])
        return res


class account_invoice(models.Model):
    _inherit = "account.invoice"

    move_niif = fields.Many2one('account.move', string='Reconocimiento Ingreso', readonly=True)


    @api.multi
    def action_cancel(self):
        self = self.with_context(factura=True)
        res = super(account_invoice, self).action_cancel()
        if self.move_niif:
            self._cr.execute("DELETE FROM account_move WHERE id=%s", (self.move_niif.id,))
        return res


    @api.multi
    def action_move_create(self):
        res = super(account_invoice, self).action_move_create()
        sale_id = False
        if self.origin:
            sale_id = self.env['sale.order'].search([('name', '=', self.origin)])

        if self.type == 'out_invoice' and self.company_id.niif_income and (self.stock_picking_id and self.stock_picking_id.move_income_niif or sale_id):
            move_line_obj = self.env['account.move.line']
            account_move_obj = self.env['account.move']
            if sale_id:
                journal_id=self.journal_id.id
            else:
                journal_id=self.stock_picking_id.move_income_niif.journal_id.id

            move = {
                'name':'RECNOCIMIENTO DE INGRESOS'+' '+self.origin,
                'line_id': [],
                'journal_id': journal_id,
                'date': self.date_invoice,
                'period_id': self.period_id.id,
            }
            move_id = account_move_obj.create(move)

            for line in self.invoice_line:
                name=line.product_id.default_code or line.product_id.name
                analytic_account_id = line.account_analytic_id and line.account_analytic_id.id or False
                account_id = line.product_id.categ_id.account_income_niif and line.product_id.categ_id.account_income_niif.id or False
                if not account_id:
                    raise osv.except_osv(_('Configuration !'), _("DEbe configurar la cuenta de provision de ingresos niif en la categoria '%s'"  % line.product_id.categ_id.name))

                if sale_id:
                    output_account_id = self.partner_id.account_reserve_niif and self.partner_id.account_reserve_niif.id or False
                else:
                    output_account_id = self.partner_id.account_income_niif and self.partner_id.account_income_niif.id or False

                if not output_account_id:
                    raise osv.except_osv(_('Configuration !'), _("Debe configurar la cuenta de provision de ingresos en el cliente '%s'."  % self.partner_id.name))

                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, account_niif_id, analytic_account_id, partner_id, debit, credit, date, state) VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id.id, self.company_id.id, journal_id, name, self.period_id.id, output_account_id, output_account_id, analytic_account_id or None, self.partner_id.id, 0.0, line.price_unit*line.quantity, self.date_invoice, 'valid'))

                self._cr.execute('''INSERT INTO account_move_line (move_id, company_id, journal_id, name, period_id, account_id, account_niif_id, analytic_account_id, partner_id, debit, credit, date, state) VALUES
                        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''' , (move_id.id, self.company_id.id, journal_id, name, self.period_id.id, account_id, account_id, analytic_account_id or None, self.partner_id.id,  line.price_unit*line.quantity, 0.0, self.date_invoice, 'valid'))

            move_id.post()
            self.move_niif = move_id.id



        return res
#
