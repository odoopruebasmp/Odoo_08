# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp
from openerp.addons.avancys_orm import avancys_orm as avo

import progressbar


class stock_report_quants_line(models.Model):
    _name = 'stock.report.quants.line'
    _order = "id desc"

    product = fields.Char(string='Producto')
    ref = fields.Char(string='Referencia')
    qty = fields.Float(string='Cantidad', digits_compute=dp.get_precision('Product UoM'))
    lot_id = fields.Many2one('stock.production.lot', string='Lote')
    location_id = fields.Many2one('stock.location', string='Ubicacion')
    date = fields.Datetime(string='Fecha Entrada')
    cost = fields.Float(string='Costo Unitario', digits=dp.get_precision('Account'))
    cost_total = fields.Float(string='Costo Total', digits=dp.get_precision('Account'))
    quant_id = fields.Many2one('stock.quant', string='Quant')
    date_start = fields.Datetime(string='Fecha Inicial', required=True)
    date_end = fields.Datetime(string='Fecha Final', required=True)
        

class stock_report_quants_wizard(models.TransientModel):
    _name = 'stock.report.quants.wizard'

    print_report = fields.Selection([('print', 'Excel'),('analizar', 'Analizar')], string='Visualizacion', required=True, default='print')
    loc_type = fields.Selection([('supplier', 'Ubicacion del Proveedor'),
                                 ('view', 'Ver'),
                                 ('internal', 'Ubicacion Interna'),
                                 ('customer', 'Ubicacion del Cliente'),
                                 ('inventory', 'Inventario'),
                                 ('procurement', 'Abastecimiento'),
                                 ('production', 'Produccion'),
                                 ('transit', 'Ubicacion de Transito'),
                                 ('all', 'TODAS')], string='Tipo de Ubicacion',required=True, default='internal')
    date_start = fields.Datetime(string='Fecha Inicial', required=True, default=datetime.now()-timedelta(days=datetime.now().day - 1) -timedelta(hours=datetime.now().hour - 5))
    date_end = fields.Datetime(string='Fecha Final', required=True, default=datetime.now())
    group_location_ids = fields.Many2one('stock.report.sql.group.location', string='Ubicaciones', help="Deje vacio este campo si desea seleccionar todas las ubicaciones")
    group_product_ids = fields.Many2one('stock.report.sql.group.product', string='Productos', help="Deje vacio este campo si desea seleccionar todas los productos")

    @api.multi
    def calc_report(self):
        report_line_obj = self.env['stock.report.quants.line']
        product_obj = self.env['product.product']
        location_obj = self.env['stock.location']
        orm2sql = self.env['avancys.orm2sql']
        cr = self._cr
        uid = self._uid
        dt_start = self.date_start
        dt_end = self.date_end

        if self.group_product_ids:
            product_ids = tuple([x.id for x in self.group_product_ids.product_ids])
        else:
            product_ids = tuple([x.id for x in product_obj.search([('active','=',True),('type','=','product')])])

        if self.group_location_ids:
            if self.loc_type == 'all':
                location_ids = tuple([x.id for x in self.group_location_ids.location_ids])
            else:
                location_ids = tuple([x.id for x in self.group_location_ids.location_ids if x.usage == self.loc_type])
        else:
            if self.loc_type == 'all':
                location_ids = tuple([x.id for x in location_obj.search([('active','=',True)])])
            else:
                location_ids = tuple([x.id for x in location_obj.search(['|', ('active', '=', False), ('active', '=', True),
                                                                         ('usage', '=', self.loc_type)])])

        self._cr.execute(''' DELETE FROM stock_report_quants_line WHERE create_uid = %s''' % uid)

        self._cr.execute('''SELECT  sq.id,
                                    pt.name,
                                    pp.default_code,
                                    sq.location_id,
                                    sq.qty,
                                    sq.cost,
                                    sq.in_date,
                                    sq.lot_id
                            FROM    stock_quant sq,
                                    product_template pt,
                                    stock_location sl,
                                    product_product pp 
                            WHERE   sq.product_id in %s
                                AND sq.location_id in %s
                                AND sq.location_id = sl.id
                                AND sq.product_id = pp.id
                                AND pt.id = pp.product_tmpl_id''',
                            (product_ids, location_ids))
        result = self._cr.fetchall()
        i, bar = 0, progressbar.ProgressBar(max_value=len(result), redirect_stdout=True,
                                            redirect_stderr=True, widgets=orm2sql.widgets()).start()
        for res in result:
            quant_id = res[0]
            product_name = res[1] or 'Indefinido'
            default_code = res[2] or 'Indefinido'
            location_id = res[3] or False
            qty = float(res[4]) or 0.0
            cost = float(res[5]) or 0.0
            in_date = res[6] or False
            lot_id = res[7] or False
            ct = cost * qty

            values = {
                'product': product_name,
                'ref': default_code,
                'qty': qty,
                'lot_id': lot_id,
                'location_id': location_id,
                'date': in_date,
                'cost': cost,
                'cost_total': ct,
                'date_start': dt_start,
                'date_end': dt_end,
                'quant_id': quant_id
            }
            avo.direct_create(cr, uid, 'stock_report_quants_line', [values])

            i += 1
            bar.update(i, bar.widgets[7].update_mapping(item=product_name))

        if self.print_report == 'print':
            datas = {
                'ids': [x.id for x in report_line_obj.search([('create_uid', '=', uid)])],
                'model': 'stock.report.quants.line'
            }
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'report_odoo_extended.reporte_stock_quants_aeroo',
                'report_type': 'aeroo',
                'datas': datas,
            }
        else:    
            return {
                'name': 'Analisis de Quants',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'stock.report.quants.line',
                'type': 'ir.actions.act_window'
            }
