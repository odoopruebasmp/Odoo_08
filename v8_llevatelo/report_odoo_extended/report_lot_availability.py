# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import xlsxwriter

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.http import request
from openerp.addons.avancys_orm import avancys_orm
from openerp.exceptions import Warning


class StockReportLotAvailability(models.Model):
    _name = 'stock.report.lot.availability'
    _order = "product_ref,location,lot"

    product = fields.Char('Producto', readonly=True)
    product_ref = fields.Char('Ref. Producto', readonly=True)
    product_name = fields.Char('Nombre Producto', readonly=True)
    location = fields.Char(u'Ubicación Origen', readonly=True)
    lot = fields.Char('Lote', readonly=True)
    qty = fields.Float(string='Cantidad', digits_compute=dp.get_precision('Product UoM'), readonly=True)


class StockReportLotAvailabilityWizard(models.TransientModel):
    _name = 'stock.report.lot.availability.wizard'

    print_report = fields.Selection([('print', 'Excel'), ('analizar', 'Analizar')], string='Visualizacion',
                                    required=True, default='print')
    recreate = fields.Boolean('Recrear Quants', help='Marque este check para correr el proceso de recreación de quants '
                                                     'basado en los movimientos de inventario. Este proceso solo puede '
                                                     'ser generado por el usuario administrador.')
    product_ids = fields.Many2many('product.product', string='Productos')
    location_ids = fields.Many2many('stock.location', string='Ubicaciones', domain=[('usage', '=', 'internal')])

    @api.multi
    def calc(self, *args):
        uid = self._uid
        cr = self._cr
        if self.recreate and uid != 1 and 'from_transfer' not in args:
            raise Warning(u"Este proceso puede ser generado únicamente por el usuario administrador, por favor "
                          u"contacte a Soporte")

        # ELIMINANDO  REGISTROS
        self._cr.execute(''' DELETE FROM stock_report_lot_availability WHERE create_uid = %s''' % uid)

        cr.execute('''
        select id,sum(smqty),sum(spoqty) from (
                  select pp.id,
                         sum(sm.product_qty) as smqty,0 as spoqty
                  from stock_picking sp
                           inner join stock_move sm on sp.id = sm.picking_id
                           inner join stock_location sl on sm.location_id = sl.id and sl.usage!='internal'
                           inner join stock_location sl2 on sm.location_dest_id = sl2.id and sl2.usage='internal'
                           inner join product_product pp on sm.product_id=pp.id
                  where sp.state = 'done'
                  group by pp.id
                  union
                  select pp.id,
                         0 as smqty,sum(spo.product_qty) as spoqty
                  from stock_picking sp
                           inner join stock_pack_operation spo on sp.id = spo.picking_id
                           inner join stock_location sl on spo.location_id = sl.id and sl.usage!='internal'
                           inner join stock_location sl2 on spo.location_dest_id = sl2.id and sl2.usage='internal'
                           inner join product_product pp on spo.product_id=pp.id
                  where sp.state = 'done'
                  group by pp.id
              ) as con group by id having sum(smqty) != sum(spoqty);
        ''')
        in_products = cr.fetchall()
        in_products = [x[0] for x in in_products]  # Productos ingresados con diferencias en los move y pack operation

        cr.execute('''
                select id,sum(smqty),sum(spoqty) from (
                          select pp.id,
                                 sum(sm.product_qty) as smqty,0 as spoqty
                          from stock_picking sp
                                   inner join stock_move sm on sp.id = sm.picking_id
                                   inner join stock_location sl on sm.location_id = sl.id and sl.usage='internal'
                                   inner join stock_location sl2 on sm.location_dest_id = sl2.id and sl2.usage!='internal'
                                   inner join product_product pp on sm.product_id=pp.id
                          where sp.state = 'done'
                          group by pp.id
                          union
                          select pp.id,
                                 0 as smqty,sum(spo.product_qty) as spoqty
                          from stock_picking sp
                                   inner join stock_pack_operation spo on sp.id = spo.picking_id
                                   inner join stock_location sl on spo.location_id = sl.id and sl.usage='internal'
                                   inner join stock_location sl2 on spo.location_dest_id = sl2.id and sl2.usage!='internal'
                                   inner join product_product pp on spo.product_id=pp.id
                          where sp.state = 'done'
                          group by pp.id
                      ) as con group by id having sum(smqty) != sum(spoqty);
                ''')
        out_products = cr.fetchall()
        out_products = [x[0] for x in out_products]  # Productos egresados con diferencias en los move y pack operation

        if self.product_ids:
            product_list = self.product_ids
        else:
            product_list = self.env['product.product'].search([('type', '=', 'product'), ('is_asset', '=', False)])

        to_remove_products = list(set(in_products + out_products))
        product_list = product_list.filtered(lambda x: x.id not in to_remove_products)
        product_list = ','.join(str(x.id) for x in product_list)
        if self.location_ids:
            # noinspection PyProtectedMember
            location_ids = ','.join(str(x.id) for x in self.location_ids if x.usage == 'internal')
        else:
            cr.execute("select id from stock_location where usage='internal'")
            location_ids = cr.fetchall()
            location_ids = [x[0] for x in location_ids]
            location_ids = ','.join(str(x) for x in location_ids)
        
        if not product_list or not location_ids:
          return True

        cr.execute('''
                    SELECT 
                        product_ref,product_name,location,lot,sum(qty),pid,slid,splid
                    FROM (
                     ----INGRESOS---
                     --PICKING--
                      SELECT 
                        pp.default_code as product_ref,pp.name_template as product_name,sl.complete_name as location,
                        spl.name as lot,SUM(spo.product_qty) as qty,pp.id as pid,sl.id as slid,spl.id as splid
                      FROM 
                        stock_pack_operation spo
                        INNER JOIN stock_picking sp ON spo.picking_id = sp.id
                        INNER JOIN product_product pp ON spo.product_id = pp.id
                        LEFT JOIN stock_location sl ON spo.location_dest_id = sl.id
                        LEFT JOIN stock_production_lot spl ON spo.lot_id = spl.id
                      WHERE
                        spo.product_id IN ({prod})
                        AND spo.location_dest_id IN ({loc})
                        AND sp.state = 'done'
                      GROUP BY
                        pp.default_code,
                        pp.name_template,
                        sl.complete_name,
                        spl.name,
                        pp.id,
                        sl.id,
                        spl.id
                      UNION
                      --NO PICKING--
                      SELECT
                        pp.default_code as product_ref,pp.name_template as product_name,sl.complete_name as location,
                        spl.name as lot,SUM(sm.product_qty) as qty,pp.id as pid,sl.id as slid,spl.id as splid
                      FROM 
                        stock_move sm
                        INNER JOIN product_product pp ON sm.product_id = pp.id
                        LEFT JOIN stock_location sl ON sm.location_dest_id = sl.id
                        LEFT JOIN stock_production_lot spl ON sm.restrict_lot_id = spl.id
                      WHERE
                        sm.product_id IN ({prod})
                        AND sm.location_dest_id IN ({loc})
                        AND sm.picking_id IS NULL
                        AND sm.state = 'done'
                      GROUP BY
                        pp.default_code,
                        pp.name_template,
                        sl.complete_name,
                        spl.name,
                        pp.id,
                        sl.id,
                        spl.id
                      UNION
                      ---SALIDAS---
                      --PICKING--
                      SELECT 
                        pp.default_code as product_ref,pp.name_template as product_name,sl.complete_name as location,
                        spl.name as lot,-1*SUM(spo.product_qty) as qty,pp.id as pid,sl.id as slid,spl.id as splid
                      FROM 
                        stock_pack_operation spo
                        INNER JOIN stock_picking sp ON spo.picking_id = sp.id
                        INNER JOIN product_product pp ON spo.product_id = pp.id
                        LEFT JOIN stock_location sl ON spo.location_id = sl.id
                        LEFT JOIN stock_production_lot spl ON spo.lot_id = spl.id
                      WHERE
                        spo.product_id IN ({prod})
                        AND spo.location_id IN ({loc})
                        AND sp.state = 'done'
                      GROUP BY
                        pp.default_code,
                        pp.name_template,
                        sl.complete_name,
                        spl.name,
                        pp.id,
                        sl.id,
                        spl.id
                      UNION
                      --NO PICKING--
                      SELECT 
                        pp.default_code as product_ref,pp.name_template as product_name,sl.complete_name as location,
                        spl.name as lot,-1*SUM(sm.product_qty) as qty,pp.id as pid,sl.id as slid,spl.id as splid
                      FROM 
                        stock_move sm
                        INNER JOIN product_product pp ON sm.product_id = pp.id
                        LEFT JOIN stock_location sl ON sm.location_id = sl.id
                        LEFT JOIN stock_production_lot spl ON sm.restrict_lot_id = spl.id
                      WHERE
                        sm.product_id IN ({prod})
                        AND sm.location_id IN ({loc})
                        AND sm.picking_id IS NULL
                        AND sm.state = 'done'
                      GROUP BY
                        pp.default_code,
                        pp.name_template,
                        sl.complete_name,
                        spl.name,
                        pp.id,
                        sl.id,
                        spl.id
                      ) as con group by product_ref, product_name, location, lot, pid, slid, splid
        '''.format(prod=product_list, loc=location_ids))
        result = cr.fetchall()
        print(len(result))
        for i, res in enumerate(result):
            if abs(res[4] or 0) > 0:
                dlines = {
                    'product': u'[{}] {}'.format(res[0], res[1]),
                    'product_ref': res[0] or 'NULO',
                    'product_name': res[1] or 'NULO',
                    'location': res[2] or 'NULO',
                    'lot': res[3] or 'NULO',
                    'qty': res[4]
                }
                avancys_orm.direct_create(cr, uid, 'stock_report_lot_availability', [dlines])
            print(i)
        if self.recreate:
            cr.execute("DELETE FROM stock_quant WHERE product_id IN ({prod}) AND location_id IN ({loc})"
                       .format(prod=product_list, loc=location_ids))
            cid = self.env.user.company_id.id
            dt_now = str(datetime.now() - timedelta(hours=5))
            for i, res in enumerate(result):
                if abs(res[4] or 0) > 0:
                    dlines = {
                        'company_id': cid,
                        'in_date': dt_now,
                        'qty': res[4],
                        'product_id': res[5],
                        'location_id': res[6],
                        'lot_id': res[7] or False,
                        'cost': 0.0  # TODO
                    }
                    avancys_orm.direct_create(cr, uid, 'stock_quant', [dlines])
                print(i)

        if 'from_transfer' in args:
            return True
        if self.print_report == 'print':
            report_line_obj = self.env['stock.report.lot.availability']
            xlsx_titles = ['REF. PRODUCTO', 'PRODUCTO', 'UBICACION', 'LOTE', 'CANTIDAD']
            report_values = '''[p.product_ref, p.product_name, p.location, p.lot, p.qty]'''

            actual = str(datetime.now() - timedelta(hours=5))[0:19]
            data_attach = {
                'name': 'Disponibilidad_Lotes_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
                'datas': '.',
                'datas_fname': 'Disponibilidad_Lotes_' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
                'res_model': 'stock.report.lot.availability.wizard',
                'res_id': self.id,
            }
            self.env['ir.attachment'].search(
                [('res_model', '=', 'stock.report.lot.availability.wizard'),
                 ('company_id', '=', self.env.user.company_id.id), (
                     'name', 'like',
                     '%Disponibilidad_Lotes_%' + self.env.user.name + '%')]).unlink()  # elimina adjuntos del usuario

            # crea adjunto en blanco
            attachments = self.env['ir.attachment'].create(data_attach)

            headers = dict(request.httprequest.__dict__.get('headers'))

            if headers.get('Origin', False):
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Origin') + '/web/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            else:
                url = dict(request.httprequest.__dict__.get('headers')).get(
                    'Referer') + '/binary/saveas?model=ir.attachment&field=datas&filename_field=name&id=' + str(
                    attachments.id)
            path = attachments.store_fname
            self.env['ir.attachment'].search([['store_fname', '=', path]]).write(
                {'store_fname': attachments._get_path(path)[0]})

            wb = xlsxwriter.Workbook(attachments._get_path(path)[1])
            ws = wb.add_worksheet()
            ws_params = ('A:E', 'A1:E1', 'B', 'C', 'A5:E5')

            ws.set_column(ws_params[0], 5)
            bold = wb.add_format({'bold': True, 'fg_color': '#E0F2F7'})
            bold.set_align('center')
            text = wb.add_format({'bold': False})
            text.set_font_size(10)
            text.set_align('center')
            ws.merge_range(ws_params[1], u'Disponibilidad de Lotes', bold)
            ws.write(ws_params[2] + '3', u'Fecha Emisión:', bold)
            ws.write(ws_params[3] + '3', actual)

            ws.add_table(ws_params[4])

            for i, l in enumerate(xlsx_titles):
                ws.write(4, i, l, bold)
            for k, p in enumerate([x for x in report_line_obj.sudo().search([('create_uid', '=', self._uid)])]):
                values = eval(report_values)
                for i, l in enumerate(values):
                    ws.write(k + 5, i, l, text)

            wb.close()
            return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        else:
            return {
                'name': u'Análisis Disponibilidad de Lotes',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'stock.report.lot.availability',
                'type': 'ir.actions.act_window',
                'domain': [('create_uid', '=', self._uid)],
                'context': {'search_default_group_principal': True}
            }
