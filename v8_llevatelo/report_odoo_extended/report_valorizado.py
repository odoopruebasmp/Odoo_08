# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import xlsxwriter

from openerp import models, fields, api
import openerp.addons.decimal_precision as dp
from openerp.http import request
from openerp.addons.avancys_orm import avancys_orm
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT


class ValueLineReport(models.Model):
    _name = 'value.line.report'

    product_id = fields.Many2one('product.product', string='Producto ID')
    product_name = fields.Char(string='Producto')
    default_code = fields.Char(string='Referencia')
    location_name = fields.Char(string='Ubicación')
    qty = fields.Float(string='Cantidad')
    cost = fields.Float(string='Costo')
    total_cost = fields.Float(string='Costo Total')

class ValueReportWizard(models.TransientModel):
    _name = 'value.report.wizard'

    date_end = fields.Datetime(string='Fecha Final', required=True, default=datetime.now())
    product_ids = fields.Many2many('product.product', string='Productos')
    print_report = fields.Selection([('print', 'Excel'), ('analizar', 'Pantalla')], string='Visualizacion',
                                    required=True, default='print')
    title = fields.Char(string='titulos', default='PRODUCTO ID, PRODUCTO, REFERENCIA, UBICACION,'
                                                  'SALDO FINAL, COSTO UNITARIO, COSTO FINAL')
    product_ids = fields.Many2many('product.product', string='Productos')
    location_ids = fields.Many2many('stock.location', string='Ubicaciones')
    
    @api.multi
    def compute_value_report(self):
        cr = self._cr
        date_end = self.date_end[:10]
        query_product = ''
        if self.product_ids:
            if len(self.product_ids) > 1:
                query_product = 'and stock_move.product_id in {ids}'.format(ids=tuple(self.product_ids.ids))
            else:
                query_product = 'and stock_move.product_id = {id}'.format(id=self.product_ids.ids[0])
        
        # CREAR TABLAS
        cr.execute("""
            delete from value_line_report;
            drop table if exists prueba_cost;
            drop table if exists costo_tabla_dos;
            
            create table 
                prueba_cost as 
                    (
                        (
                            select 
                                sum(product_qty) as cantidad,
                                sum(total_cost) as total_cost,
                                stock_move.product_id,
                                sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                product_template.id 
                            from 
                                stock_move 
                            left join 
                                product_product on product_product.id=stock_move.product_id 
                            left 
                                join product_template on product_template.id=product_product.product_tmpl_id 
                            where  
                                (
                                    (
                                        select 
                                            locat.usage 
                                        from 
                                            stock_location as locat   
                                        where 
                                            locat.id=stock_move.location_id
                                    )='supplier' 
                                ) 
                            and 
                                stock_move.date <= '{date_end}' 
                            and 
                                stock_move.state='done' 
                            and  
                                product_template.type = 'product' 
                            {query_product}
                            group by 
                                stock_move.product_id,product_template.id 
                            order by 
                                stock_move.product_id
                        ) 
                        union all  
                            (
                                select 
                                    sum(product_qty) * -1  as cantidad, 
                                    sum(total_cost) * -1  as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id 
                                from 
                                    stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id 
                                where 
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location  as locat   
                                            where locat.id=stock_move.location_dest_id)='supplier' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done' 
                                and 
                                    product_template.type = 'product' 
                                {query_product}
                                group by 
                                    stock_move.product_id,
                                    product_template.id 
                                order by 
                                    stock_move.product_id
                            ) 
                        union all 
                            (
                                select 
                                    sum(product_qty) * -1  as cantidad, 
                                    sum(total_cost) * -1  as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id 
                                from 
                                    stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id  
                                where  
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location  as locat   
                                            where 
                                                locat.id=stock_move.location_dest_id)='customer' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done'  
                                and 
                                    product_template.type = 'product'  
                                {query_product}
                                group by 
                                    stock_move.product_id,
                                    product_template.id 
                                order by 
                                    stock_move.product_id
                            ) 
                        union all   
                            (
                                select 
                                    sum(product_qty) as cantidad, 
                                    sum(total_cost) as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id from stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id 
                                where  
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location as locat    
                                            where 
                                                locat.id=stock_move.location_id
                                        )='customer' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done' 
                                and  
                                    product_template.type = 'product' 
                                {query_product}
                                group by 
                                    stock_move.product_id,
                                    product_template.id 
                                order by 
                                    stock_move.product_id
                            )
                        union all 
                            (
                                select 
                                    sum(product_qty) as cantidad, 
                                    sum(total_cost) as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo,  
                                    product_template.id 
                                from 
                                    stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id 
                                where 
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location as locat   
                                            where 
                                                locat.id=stock_move.location_id
                                        )='production' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done' 
                                and  
                                    product_template.type = 'product' 
                                {query_product}
                                group by 
                                    stock_move.product_id,product_template.id 
                                order by 
                                    stock_move.product_id
                            ) 
                        union all  
                            (
                                select 
                                    sum(product_qty) * -1  as cantidad, 
                                    sum(total_cost) * -1  as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id 
                                from 
                                    stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id  
                                where  
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location  as locat  
                                            where 
                                                locat.id=stock_move.location_dest_id
                                        )='production' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done'  
                                and 
                                    product_template.type = 'product'  
                                {query_product}
                                group by 
                                    stock_move.product_id,
                                    product_template.id 
                                order by 
                                    stock_move.product_id
                            ) 
                        union all 
                            (
                                select 
                                    sum(product_qty) * -1  as cantidad, 
                                    sum(total_cost) * -1  as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id from stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id  
                                where 
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location  as locat    
                                            where 
                                                locat.id=stock_move.location_dest_id
                                        )='inventory' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done' 
                                and 
                                    product_template.type = 'product' 
                                {query_product}
                                group by 
                                    stock_move.product_id,product_template.id 
                                order by 
                                    stock_move.product_id
                            ) 
                        union all 
                            (
                                select 
                                    sum(product_qty) as cantidad, 
                                    sum(total_cost) as total_cost, 
                                    stock_move.product_id, 
                                    sum(total_cost)/(case when sum(product_qty)=0 then 1 else sum(product_qty) end ) as costo, 
                                    product_template.id 
                                from 
                                    stock_move 
                                left join 
                                    product_product on product_product.id=stock_move.product_id 
                                left join 
                                    product_template on product_template.id=product_product.product_tmpl_id  
                                where  
                                    (
                                        (
                                            select 
                                                locat.usage 
                                            from 
                                                stock_location as locat  
                                            where 
                                                locat.id=stock_move.location_id
                                        )='inventory' 
                                    ) 
                                and 
                                    stock_move.date <= '{date_end}' 
                                and 
                                    stock_move.state='done' 
                                and 
                                    product_template.type = 'product' 
                                {query_product}
                                group by 
                                    stock_move.product_id,
                                    product_template.id 
                                order by 
                                    stock_move.product_id
                            )
                    );
		
            create table 
                costo_tabla_dos as 
                    ( 
                        select 
                            sum(cantidad) as cantidad, 
                            sum(total_cost) as costo_total, 
                            sum(total_cost)/ (case when sum(cantidad)=0 then 1 else sum(cantidad) end ) as costo , 
                            product_id,
                            id 
                        from 
                            prueba_cost  
                        group by  
                            product_id,
                            id  
                        order by 
                        id 
                    ); 
        
        """.format(date_end=date_end,
                   query_product=query_product))

        # CONSULTA DE INFORMACION
        cr.execute("""
            SELECT 
                sum(costo_total),
                sum(cantidad), 
                product_id, 
                sum(costo) 
            FROM 
                costo_tabla_dos 
            GROUP BY 
                product_id;
        """)

        result = cr.fetchall()

        if result:
            for r in result:
                cr.execute("""
                    select 
                        name_template, 
                        default_code 
                    from 
                        product_product 
                    where 
                        id = {id}
                """.format(id=r[2]))
                product_id = cr.fetchone()
                
                if product_id[0] is None:
                    product_name = 'Sin nombre'
                else:
                    product_name = product_id[0]
                if product_id[1] is None:
                    default_code = 'Sin Referencia'
                else:
                    default_code = product_id[1]
                
                line = {
                        'product_id': r[2],
                        'product_name': product_name,
                        'default_code': default_code,
                        'location_name': 'Todas las Ubicaciones',
                        'qty': r[1],
                        'cost': r[3],
                        'total_cost': r[0],
                    }
                avancys_orm.direct_create(self._cr, self._uid, 'value_line_report', [line])
        else:
            line = {
                'product_name': 'Sin resultado',
                'qty': 0,
                'total_cost': 0,
                'cost': 0
            }
            avancys_orm.direct_create(self._cr, self._uid, 'value_line_report', [line])
        
        if self.print_report == 'print':
            cr.execute("""
                        select
                            product_id,
                            product_name,
                            default_code,
                            location_name,
                            qty,
                            cost,
                            total_cost
                        from
                            value_line_report
                    """)
            datos = self._cr.fetchall()
            url = self.printfast(datos)
            return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}
        else:
            return {
                'name': 'Analisis de Valorizado',
                'view_type': 'form',
                'view_mode': 'graph,tree',
                'view_id': False,
                'res_model': 'value.line.report',
                'type': 'ir.actions.act_window',
                'context': {'search_default_group_principal': True}
            }

    @api.multi
    def printfast(self, datos):
        actual = str(datetime.now() - timedelta(hours=5))[0:19]
        data_attach = {
            'name': 'Valorizado_V2' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.xlsx',
            'datas': '.',
            'datas_fname': 'Valorizado_V2' + self.env.user.company_id.name + self.env.user.name + '_' + actual + '.',
            'res_model': 'value.report.wizard',
            'res_id': self.id,
        }
        self.env['ir.attachment'].search(
            [('res_model', '=', 'value.report.wizard'), ('company_id', '=', self.env.user.company_id.id), (
                'name', 'like',
                '%Valorizado_V2%' + self.env.user.name + '%')]).unlink()  # elimina adjuntos del usuario

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
        bold = wb.add_format({'bold': True})
        bold2 = wb.add_format({'bold': True, 'fg_color': '#ffffff'})
        bold3 = wb.add_format({'bold': False, 'fg_color': '#F2F2F2'})
        bold4 = wb.add_format({'bold': True, 'fg_color': '#2E86C1'})
        bold.set_align('center')
        bold2.set_align('center')
        bold3.set_align('center')
        bold4.set_align('center')
        money_format = wb.add_format({'num_format': '$#,##0'})
        money_format.set_align('right')
        ws = wb.add_worksheet('Valorizado')
        ws.set_column('A:A', 20)
        ws.set_column('B:B', 30)
        ws.set_column('C:C', 30)
        ws.set_column('D:D', 20)
        ws.set_column('E:E', 20)
        ws.set_column('F:F', 20)
        ws.set_column('G:G', 20)

        abc = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U',
               'V', 'W', 'X', 'Y', 'Z']

        ws.merge_range('A1:G1', 'INFORME VALORIZADO', bold2)
        ws.merge_range('A2:G2', 'FECHA CONSULTA: ' + actual, bold2)

        ws.merge_range('A3:B4', '', bold2)
        ws.write('C3', 'DESDE:', bold2)
        ws.write('D3', self.date_end, bold2)
        ws.merge_range('E3:G3', '', bold2)
        ws.merge_range('C4:G4', '', bold2)

        titulos = self.title.split(',')

        num = [x for x in range(0, 101)]
        resultado = zip(abc, num)
        for i, l in enumerate(titulos):
            for pos in resultado:
                if i == pos[1]:
                    position = pos[0]
                    break
            ws.write(position + str(5), l, bold4)
        filter_auto = 'A5:' + str(abc[len(titulos) - 1]) + '5'
        ws.autofilter(filter_auto)
        for x, line in enumerate(datos):
            for y, f in enumerate(titulos):
                for pos in resultado:
                    if y == pos[1]:
                        position = pos[0]
                        break
                if position in ('E',):
                    ws.write(position + str(6 + x), line[y] or int(0), bold3)
                elif position in ('F', 'G'):
                    ws.write(position + str(6 + x), line[y] or int(0), money_format)
                else:
                    ws.write(position + str(6 + x), line[y] or '')
        wb.close()
        return url