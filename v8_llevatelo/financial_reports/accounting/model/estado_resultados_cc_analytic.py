# -*- coding: utf-8 -*-
from datetime import datetime

import openerp.addons.decimal_precision as dp
from openerp import models, fields, api, _
from openerp.exceptions import Warning


class AccountFinancialReportsAccountingPygCcAnalytic(models.Model):
    _name = 'fpa.pyg.cc.analytic'

    date = fields.Datetime(string='Fecha')
    date_from = fields.Date(string='Fecha Inicial')
    date_to = fields.Date(string='Fecha Final')
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')],
                              default='validados', string='Estados')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    chart_account_id = fields.Many2one('account.account', string='Plan Contable', help='Select Charts of Accounts',
                                       required=True, domain=[('parent_id', '=', False)])


class AccountFinancialReportsAccountingPygCcAnalyticLine(models.Model):
    _name = 'fpa.pyg.cc.analytic.line'

    account_id = fields.Many2one('account.account', string='Cuenta', ondelete='cascade')
    nivel = fields.Integer(string="Nivel")
    analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta analitica', ondelete='cascade')
    amount_inicial = fields.Float(string='Saldo Inicial', digits=dp.get_precision('Account'))
    debit = fields.Float(string='Debito', digits=dp.get_precision('Account'))
    credit = fields.Float(string='Credito', digits=dp.get_precision('Account'))
    amount_final = fields.Float(string='Saldo Final', digits=dp.get_precision('Account'))
    amount_1 = fields.Float(string='Saldo Año 1', digits=dp.get_precision('Account'))
    amount_2 = fields.Float(string='Saldo Año 2', digits=dp.get_precision('Account'))
    amount_3 = fields.Float(string='Saldo Año 3', digits=dp.get_precision('Account'))
    amount_4 = fields.Float(string='Saldo Año 4', digits=dp.get_precision('Account'))
    amount_5 = fields.Float(string='Saldo Año 5', digits=dp.get_precision('Account'))
    cuenta = fields.Char(string='Cuenta')
    cc1 = fields.Char(string='cc1')
    cc2 = fields.Char(string='cc2')
    cc3 = fields.Char(string='cc3')
    cc4 = fields.Char(string='cc4')
    cc5 = fields.Char(string='cc5')
    sequence = fields.Integer(string="Secuencia", required=False, help='Secuencia en la cual se muestran en la vista')
    company_id = fields.Many2one('res.company', string='Compañia')
    user_id = fields.Many2one('res.users', string='Usuario')
    resume = fields.Boolean(string="Resumen")
    bold = fields.Boolean(string="Bold", default=False)
    encabezado_id = fields.Many2one('fpa.pyg.cc.analytic', string='Encabezado', ondelete='cascade')
    financial_id = fields.Many2one('fpa.financial.reports', string='Reporte')
    concepts_id = fields.Many2one('fpa.financial.reports.concepts', string='Conceptos', ondelete='cascade')


class WizardAccountFinancialReportsAccountingPygCcAnalytic(models.TransientModel):
    _name = 'fpa.pyg.cc.analytic.wizard'

    def _set_niveles(self):
        return self.env['fpa.niveles'].\
            search([('financial_reports', '=', self.env.context.get('active_ids', False)), ('code', 'in', ('99', '100'))])

    def _get_domain(self):
        return [('financial_reports', '=', self.env.context.get('active_ids', False))]

    account_filter = fields.Boolean(string="Filtro adicional de cuentas")
    partner_filter = fields.Boolean(string="Filtro adicional de terceros")
    journal_filter = fields.Boolean(string="Filtro adicional de diarios")
    analytic_filter = fields.Boolean(string="Filtro adicional de cuenta analitica")
    cierre = fields.Boolean(string="Cierre")
    chart_account_id = fields.Many2one('account.account', string='Plan Contable',
                                       help='Select Charts of Accounts', required=True,
                                       domain=[('parent_id', '=', False)])
    company_id = fields.Many2one('res.company', related='chart_account_id.company_id', string='Company', readonly=True)
    period_balance_ids = fields.Many2many('account.period', string='Periodos')
    journal_ids = fields.Many2many('account.journal', string='Diarios')
    partner_ids = fields.Many2many('res.partner', string='Terceros')
    account_ids = fields.Many2many('account.account', string='Cuentas', domain=[('type', '!=', 'view')])
    analytic_ids = fields.Many2many('account.analytic.account', string='Cuentas analiticas', 
                                    domain=[('type', '!=', 'view')])
    date_from = fields.Date(string="Fecha Inicial", required=True)
    date_to = fields.Date(string="Fecha Final", required=True)
    estado = fields.Selection([('borrador', 'Borrador'), ('validados', 'Validados'), ('todos', 'Todos')], 
                              default='todos', string='Estados', required=True)
    niveles = fields.Many2many('fpa.niveles', string='Niveles', help='Seleccione los niveles para la consulta.',
                               default=_set_niveles, domain=_get_domain, required=True)

    @api.one
    @api.onchange('chart_account_id')
    def get_filter(self):
        active_id = self.env.context.get('active_ids', False)
        financial_reports = self.env['fpa.financial.reports'].browse(active_id)
        self.account_filter = financial_reports.account_filter
        self.partner_filter = financial_reports.partner_filter
        self.journal_filter = financial_reports.journal_filter
        self.analytic_filter = financial_reports.analytic_filter

    @api.one
    @api.constrains('date_from', 'date_to')
    def _validar_fechas(self):
        if self.date_from > self.date_to:
            raise Warning(_('Error en las fechas!'), _("Las fechas planificadas estan mal configuradas"))

    @api.multi
    def generar(self):
        company = self.company_id
        user = self.env.user
        cr = self.env.cr
        
        dt_now = datetime.now()
        dt_from = self.date_from
        dt_to = self.date_to
        states = self.estado
        chart_account = self.chart_account_id

        niveles = [x.code for x in self.niveles]
        cr.execute(''' select count(*) from fpa_pyg_cc_analytic_line ''')
        count = cr.fetchone()[0]
        financial_reports = self.env['fpa.financial.reports'].browse(self.env.context['active_id'])
        # truncate a la tabla cuando sean mas de 1millón de registros, para que no tarde tanto eliminando las lineas
        if count > 1000000:
            cr.execute(''' TRUNCATE fpa_pyg_cc_analytic_line ''')
            cr.execute(''' TRUNCATE fpa_pyg_cc_analytic ''')
        else:
            cr.execute("DELETE FROM fpa_pyg_cc_analytic_line WHERE financial_id=%s AND company_id = %s and user_id = %s"
                       % (financial_reports.id, company.id, user.id))
            cr.execute("DELETE FROM fpa_pyg_cc_analytic WHERE financial_id=%s AND company_id = %s and user_id = %s" %
                       (financial_reports.id, company.id, user.id))
        where = ''
        cuenta = []
        # Cuentas
        if financial_reports:
            if financial_reports.concepts_ids:
                for conceptos in financial_reports.concepts_ids:
                    for cuentas in conceptos.account_ids:
                        cuenta.append(cuentas.id)
        if len(cuenta) > 0:
            where += 'AND ( aml.account_id IN ({}) )'.format(','.join(str(x) for x in cuenta))

        # Agrega encabezado con parametros indicados por el usuario
        sql = " INSERT INTO fpa_pyg_cc_analytic(date, date_from, date_to, estado, company_id, user_id,chart_account_id, " \
              "financial_id) VALUES ('%s','%s','%s','%s',%s,%s,%s,%s) RETURNING ID " % \
              (dt_now, dt_from, dt_to, states, company.id, user.id, chart_account.id, financial_reports.id)
        cr.execute(sql)
        encabezado_id = False
        try:
            encabezado_id = cr.fetchone()[0]
        except ValueError:
            pass

        if self.journal_ids:
            where += ''' AND aml.journal_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.journal_ids))
        if self.account_ids:
            if chart_account.niif:
                where += ''' AND aml.account_niif_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            else:
                where += ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
        if self.partner_ids:
            where += ''' AND aml.partner_id in (%s) ''' % (
                ','.join(str(x.id) for x in self.partner_ids))

        cuenta_analitica = ' aal.account_id '

        if self.analytic_ids:
            where += ''' AND aal.account_id in (%s) ''' % (','.join(str(x.id) for x in self.analytic_ids))

        if states == 'borrador':
            estado = 'draft'
        elif states == 'validados':
            estado = 'valid'
        else:
            estado = '%'
        where += ''' AND aml.state like '%s' ''' % estado

        # verificar si tiene el modulo de niif_account instalado
        module = self.env['ir.module.module'].search([('name', '=', 'niif_account'), ('state', '=', 'installed')])
        # agregar condición de cuentas indicadas en el wizard
        condition = 'aa.id = movimientos.account_id'
        account = 'aml.account_id'
        where_add = ''
        if self.account_ids:
            where_add = ''' AND aml.account_id in (%s) ''' % (','.join(str(x.id) for x in self.account_ids))
            if module:
                if chart_account.niif:
                    where_add = ''' AND aml.account_niif_id in (%s) ''' % (
                        ','.join(str(x.id) for x in self.account_ids))
        if module:
            if chart_account.niif:
                condition = 'aa.id = account_id'
                account = 'aml.account_niif_id'
        where += where_add

        relation = ' LEFT '
        if financial_reports.concepts_ids:
            relation = ' INNER '

        mov_cierre = ' '
        # if self.cierre is True:
        #     # TODO
        #     mov_cierre = " UNION SELECT %s, %s::integer, sum(aml.debit) as debit, sum(aml.credit) as credit " \
        #                  " FROM account_move_line aml " \
        #                  " INNER JOIN account_period ap on ap.id = aml.period_id " \
        #                  " WHERE  aml.company_id = %s AND (aml.date BETWEEN '%s' AND '%s') and ap.special IS TRUE " \
        #                  " %s " \
        #                  " GROUP BY analytic_account_id, %s " % (
        #                  account, cuenta_analitica, user.company_id.id, dt_from, dt_to, where,
        #                  account)

        cr.execute('''INSERT INTO fpa_pyg_cc_analytic_line
                        (nivel,sequence,bold,user_id,company_id,account_id,cuenta,analytic_account_id,cc1,cc2,cc3,cc4,
                         cc5,concepts_id,debit,credit,amount_final,encabezado_id,resume,financial_id)
                      SELECT 99,ffrc.sequence,False,{uid},{cid},account_id,aa.code,analytic_account_id,aaa.cc1,aaa.cc2,
                          aaa.cc3,aaa.cc4,aaa.cc5,ffrc.id as concepts_id,sum(debit) AS debit,sum(credit) AS credit,
                          sum(debit-credit) as amount_final, {enc}::integer as encabezado_id,False,{fid}
                      FROM (
                          SELECT
                              {acc} as account_id,
                              {acn}::integer as analytic_account_id,
                              SUM(CASE WHEN aal.amount < 0 THEN -1*aal.amount ELSE 0 END) as debit,
                              SUM(CASE WHEN aal.amount > 0 THEN aal.amount ELSE 0 END) as credit
                          FROM
                              account_move_line aml
                              INNER JOIN account_period ap on ap.id = aml.period_id
                              LEFT JOIN account_analytic_line aal ON aml.id = aal.move_id
                          WHERE 
                              aml.date BETWEEN '{dt_from}' and '{dt_to}'
                              AND aml.company_id = {cid}
                          {wh}
                          GROUP BY
                            {acn},
                            {acc}
                          {mvc}
                      ) AS movimientos
                        INNER JOIN account_account aa ON {con} AND aa.company_id = {cid} AND aa.parent_zero = {cac}
                        {rel} JOIN fpa_financial_reports_concepts_account ffrca ON ffrca.account_account_id = aa.id
                        {rel} JOIN fpa_financial_reports_concepts ffrc on ffrc.id = ffrca.fpa_financial_reports_concepts_id
                        LEFT JOIN account_analytic_account aaa ON aaa.id = movimientos.analytic_account_id
                        INNER JOIN account_account_type aat ON aa.user_type = aat.id AND ffrc.financial_reports = {fid}
                      GROUP BY
                        ffrc.sequence,
                        account_id,
                        analytic_account_id,
                        cc1,
                        cc2,
                        cc3,
                        cc4,
                        cc5,
                        aa.code,
                        ffrc.id'''.format(uid=user.id, cid=company.id, enc=encabezado_id, fid=financial_reports.id,
                                          acc=account, acn=cuenta_analitica, dt_from=dt_from, dt_to=dt_to, wh=where,
                                          mvc=mov_cierre, con=condition, cac=chart_account.id, rel=relation))

        if '100' in niveles:
            # Agregar totales por concepto
            cr.execute('''INSERT INTO fpa_pyg_cc_analytic_line 
                            (nivel,bold,user_id,company_id,account_id,cuenta,debit,credit,amount_final,encabezado_id,
                            resume,concepts_id,financial_id)
                          SELECT
                            100,True,{uid},{cid},null,null,SUM(debit),SUM(credit),SUM(amount_final),{enc},False,ffrc.id,{fid}
                          FROM
                              fpa_financial_reports_concepts ffrc
                              LEFT JOIN fpa_pyg_cc_analytic_line fpl ON ffrc.id = fpl.concepts_id
                          WHERE
                              fpl.nivel=99
                              AND ffrc.financial_reports={fid}
                              AND fpl.user_id={uid}
                              AND fpl.company_id={cid}
                          GROUP BY
                              ffrc.id'''.format(uid=user.id, cid=company.id, enc=encabezado_id, fid=financial_reports.id))

        if '99' not in niveles:
            cr.execute("DELETE FROM fpa_pyg_cc_analytic_line WHERE nivel=99 AND user_id={} AND financial_id ={} "
                       "AND company_id={}".format(user.id, financial_reports.id, company.id))

        # Eliminar lineas sin saldo inicial, débitos y créditos
        cr.execute("DELETE FROM fpa_pyg_cc_analytic_line WHERE amount_final=0 AND debit=0 AND credit=0 AND "
                   "amount_final=0 AND user_id={} AND financial_id={} AND company_id={}"
                   .format(user.id, financial_reports.id, user.company_id.id))

        # cambia el signo
        if financial_reports.sign:
            cr.execute("UPDATE fpa_pyg_cc_analytic_line SET amount_final = amount_final * -1 WHERE user_id={} AND "
                       "financial_id ={} AND company_id={}".format(user.id, financial_reports.id, company.id))

        if financial_reports.unidades > 1:
            cr.execute('''UPDATE fpa_pyg_cc_analytic_line 
                          SET amount_inicial=amount_inicial/{unidades}, debit=debit/{unidades}, 
                              credit=credit/{unidades},amount_final=amount_final/{unidades},amount_1=amount_1/{unidades},
                              amount_2=amount_2/{unidades},amount_3=amount_3/{unidades},amount_4=amount_4/{unidades},
                              amount_5=amount_5/{unidades}
                          WHERE company_id={company_id} AND user_id={user_id} AND financial_id = {financial_id} '''
                       .format(unidades=financial_reports.unidades, financial_id=financial_reports.id, user_id=user.id,
                               company_id=user.company_id.id))

        return financial_reports.view_function(generate=False)
