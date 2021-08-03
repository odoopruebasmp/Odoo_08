# -*- coding: utf-8 -*-
from openerp import api, fields, models
from openerp.exceptions import Warning
from .hr_payroll_concept import CATEGORIES
from openerp.addons.avancys_orm import avancys_orm as orm
import xlsxwriter
import datetime
from openerp.http import request

class HrPayslipConceptReport(models.TransientModel):
    _name = 'hr.payslip.concept.report'
    _description = 'Reporte de conceptos de nomina'

    start_date = fields.Date('Fecha desde', required=True)
    end_date = fields.Date('Fecha hasta', required=True)
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    run_id = fields.Many2one('hr.payslip.run', 'Lote de nomina')
    concept_code = fields.Char('Codigo de concepto')
    category = fields.Selection(CATEGORIES, string='Categoria')
    workcenter = fields.Char('Centro de trabajo')
    payslip_type_id = fields.Many2one('hr.payslip.type', 'Tipo de nomina')
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Terminado')], string="Estado")

    @api.multi
    def generate(self):
        
        data_attach = {
            'name': 'INFORME CONCEPTOS NOMINA' + '.' + '.xlsx',
            'datas': '.',
            'datas_fname': 'INFORME CONCEPTOS NOMINA' + '.',
            'res_model': 'hr.payslip.concept.report',
            'res_id': self.id,
        }
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

        # Crear documento de Excel
        wb = xlsxwriter.Workbook(attachments._get_path(path)[1]) # Crea y da nombre al archivo de Excel
        ws = wb.add_worksheet('Reporte conceptos') # Nombre de la hoja en el archivo de Excel

        # Formato para las celdas
        cf1 = wb.add_format({'num_format': 'dd/mm/yy'})
        cf2 = wb.add_format({'num_format': '0'})
        cf3 = wb.add_format({'num_format': '@'})

        cf1.set_num_format('dd/mm/yy')
        cf2.set_num_format('#################.##')

        # CAMPOS SOLO PARA COMPAÑIAS CON TURNOS EJ COLVISEG
        self._cr.execute("SELECT state from ir_module_module where name = 'hr_roster'")
        roster = self._cr.fetchall()
        if roster and roster[0][0] == 'installed':
            cvs = True
            reg_fld = ", rr.name"
            reg_join = '''
                    LEFT JOIN account_analytic_account aaa on hc.analytic_account_id = aaa.id
                    INNER JOIN res_regional rr on aaa.regional_id = rr.id
            '''
            reg_flt = " AND rr.id = {reg}".format(reg=self.regional_id.id) if self.regional_id else " "
        else:
            cvs = False
            reg_fld, reg_join = " ", " "
            reg_flt = " "

        # FILTERS
        
        emp_flt = " AND hpc.employee_id = {e}".format(e=self.employee_id.id) if self.employee_id else " "
        lot_flt = " AND hpc.run_id = {run}".format(run=self.run_id.id) if self.run_id else " "
        cpt_flt = " AND hpc.code = '{cpt}' ".format(cpt=self.concept_code) if self.concept_code else " "
        cat_flt = " AND hpc.category = '{ctg}' ".format(ctg=self.category) if self.category else " "
        ptp_flt = " AND hp.tipo_nomina = {ptp}".format(ptp=self.payslip_type_id.id) if self.payslip_type_id else " "
        stt_flt = " AND hp.state = '{stt}'".format(stt=self.state) if self.state else " "
        wkc_flt = " AND hc.workcenter = '{wkc}'".format(wkc=self.workcenter) if self.workcenter else " "

        data_sql = '''SELECT hc.name, rp.name, hc.wage, hpc.code, hpc.name, 
                             CASE WHEN hpc.category = 'earnings' THEN '1.1 DEVENGOS'
                                  WHEN hpc.category = 'comp_earnings' THEN '1.2 ING COMPLEMENTARIOS'
                                  WHEN hpc.category = 'o_sal_earnings' THEN '1.3 OTROS ING SALARIALES'
                                  WHEN hpc.category = 'non_taxed_earnings' THEN '1.4 ING NO GRAVADOS'
                                  WHEN hpc.category = 'o_rights' THEN '1.5 OTROS DERECHOS'
                                  WHEN hpc.category = 'o_earnings' THEN '1.6 OTROS DEVENGOS'
                                  WHEN hpc.category = 'deductions' THEN '2. DEDUCCIONES'
                                  WHEN hpc.category = 'contributions' THEN '3. APORTES'
                                  WHEN hpc.category = 'provisions' THEN '4. PROVISIONES'
                                  WHEN hpc.category = 'subtotals' and hpc.code != 'NETO' THEN '5. SUBTOTALES'
                                  WHEN hpc.code = 'NETO' THEN '6. NETO'
                             END AS category,
                             hpc.amount, hpc.qty, hpc.rate, hpc.total,
                             hp.number, hpc.origin, hpc.date, pp.name, hpt.name, hpr.name, hc.workcenter, hp.state {reg_fld}
                      FROM hr_payslip_concept hpc
                      INNER JOIN hr_payslip hp on hpc.payslip_id = hp.id
                      LEFT JOIN hr_employee he on hpc.employee_id = he.id
                      LEFT JOIN res_partner rp on he.codigo = rp.ref
                      LEFT JOIN hr_contract hc on hpc.contract_id = hc.id
                      LEFT JOIN payslip_period pp on hpc.period_id = pp.id
                      LEFT JOIN hr_payslip_run hpr on hpc.run_id = hpr.id
                      LEFT JOIN hr_payslip_type hpt on hp.tipo_nomina = hpt.id
                      {reg_join}
                      WHERE hpc.date between '{ds}' and '{de}'
                      {emp_flt} {lot_flt} {cpt_flt} {cat_flt} {ptp_flt} {reg_flt} {wkc_flt}
                      ORDER BY hp.number, rp.name, category
        '''.format(reg_fld=reg_fld, reg_join=reg_join, ds=self.start_date, de=self.end_date,
                   emp_flt=emp_flt, lot_flt=lot_flt, cpt_flt=cpt_flt, cat_flt=cat_flt, ptp_flt=ptp_flt, 
                   reg_flt=reg_flt, wkc_flt=wkc_flt)
        data = orm.fetchall(self._cr, data_sql)
        # HEADERS
        ws.write(0, 0, "CONTRATO", cf3)
        ws.write(0, 1, "EMPLEADO", cf3)
        ws.write(0, 2, "SALARIO", cf3)
        ws.write(0, 3, "CODIGO", cf3)
        ws.write(0, 4, "DESCRIPCION", cf3)
        ws.write(0, 5, "CATEGORIA", cf3)
        ws.write(0, 6, "VALOR", cf3)
        ws.write(0, 7, "CANTIDAD", cf3)
        ws.write(0, 8, "APLICACION", cf3)
        ws.write(0, 9, "TOTAL", cf3)
        ws.write(0, 10, "NOMINA", cf3)
        ws.write(0, 11, "ORIGEN", cf3)
        ws.write(0, 12, "FECHA", cf3)
        ws.write(0, 13, "PERIODO", cf3)
        ws.write(0, 14, "TIPO NOMINA", cf3)
        ws.write(0, 15, "LOTE NOMINA", cf3)
        ws.write(0, 16, "CENTRO DE TRABAJO", cf3)
        ws.write(0, 17, "ESTADO", cf3)
        if cvs:
            ws.write(0, 18, "REGIONAL", cf3)

        i, j = 0, len(data)
        bar = orm.progress_bar(i, j)
        c = 0

        if len(data) > 1048500:
            raise Warning("La cantidad de registros a exportar supera los permitidos para archivos XLSX: 1048500")
        for cpt in data:
            c += 1
            ws.write(c, 0, cpt[0], cf3)
            ws.write(c, 1, cpt[1], cf3)
            ws.write(c, 2, cpt[2], cf3)
            ws.write(c, 3, cpt[3], cf3)
            ws.write(c, 4, cpt[4], cf3)
            ws.write(c, 5, cpt[5], cf3)
            ws.write(c, 6, cpt[6], cf3)
            ws.write(c, 7, cpt[7], cf3)
            ws.write(c, 8, cpt[8], cf3)
            ws.write(c, 9, cpt[9], cf3)
            ws.write(c, 10, cpt[10], cf3)
            ws.write(c, 11, cpt[11], cf3)
            ws.write(c, 12, cpt[12], cf3)
            ws.write(c, 13, cpt[13], cf3)
            ws.write(c, 14, cpt[14], cf3)
            ws.write(c, 15, cpt[15], cf3)
            ws.write(c, 16, cpt[16], cf3)
            ws.write(c, 17, cpt[17], cf3)
            if cvs:
                ws.write(c, 18, cpt[18], cf3)
            i += 1
            bar = orm.progress_bar(i, j, bar, c)

        wb.close()

        return {'type': 'ir.actions.act_url', 'url': str(url), 'target': 'self'}