# -*- coding: utf-8 -*-
from datetime import datetime
import calendar
from openerp import models, fields, api, sql_db
from openerp.addons.avancys_orm import avancys_orm as orm
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DSDF, DEFAULT_SERVER_DATETIME_FORMAT as DSTF, float_compare
from openerp.exceptions import Warning
from dateutil.relativedelta import relativedelta
import unicodedata
import base64
import math
import calendar as cal


FORM_TYPES = [
    ('E', '[E] Planilla empleados empresas'),
    # ('Y', '[Y] Planilla independientes empresas'),
    # ('A', '[A] Planilla cotizantes con novedad de ingreso'),
    # ('S', '[S] Planilla empleados de servicio domestico'),
    # ('M', '[M] Planilla mora'),
    # ('N', '[N] Planilla correcciones'),
    # ('H', '[H] Planilla madres sustitutas'),
    # ('T', '[T] Planilla empleados entidad beneficiaria del sistema general de participaciones'),
    # ('F', '[F] Planilla pago aporte patronal faltante'),
    # ('J', '[J] Planilla para pago seguridad social en cumplimiento de sentencia digital'),
    # ('X', '[X] Planilla para pago empresa liquidada'),
    # ('U', '[U] Planilla de uso UGPP para pagos por terceros'),
    # ('K', '[K] Planilla estudiantes')
]

FORM_STATES = [
    ('draft', 'Borrador'),
    ('closed', 'Cerrada')
]

#Segun el resolucion 454
TYPE_WAGE = [
    ('X', 'Integral'),
    ('F', 'Fijo'),
    ('V', 'Variable'),
    (' ', 'Aprendiz')
]

def monthrange(year=None, month=None):
    today = datetime.today()
    y = year or today.year
    m = month or today.month
    return y, m, cal.monthrange(y, m)[1]


def strip_accents(s):
    new_string = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    new_string = new_string.encode('ascii', 'replace').replace('?', ' ')
    return new_string


def prep_field(s, align='left', size=0, fill=' ', date=False):
    if s in [False, None]:
        s = ''
    if date:
        s = datetime.strftime(s, "%Y-%m-%d")
    if align == 'right':
        s = str(s)[0:size].rjust(size, str(fill))
    elif align == 'left':
        s = str(s)[0:size].ljust(size, str(fill))

    return s


def rp(value):
    if value % 100.0 >= 0.01:
        val = int(math.ceil(value / 100.0)) * 100
    else:
        val = round(value, 0)
    return val


def rp1(value):
    if value - round(value) > 0.0001:
        res = round(value) + 1
    else:
        res = round(value)
    return res


class HrContributionFormLine(models.Model):
    _name = 'hr.contribution.form.line'

    contribution_id = fields.Many2one('hr.contribution.form', 'Autoliquidacion', ondelete="cascade")
    employee_id = fields.Many2one('hr.employee', 'Empleado')
    contract_id = fields.Many2one('hr.contract', 'Contrato')
    leave_id = fields.Many2one('hr.holidays', 'Ausencia')
    main = fields.Boolean('Linea principal')

    # Campos PILA
    ing = fields.Selection([('X', 'X'), ('R', 'R'), ('C', 'C')], 'ING', help='Ingreso')
    ret = fields.Selection([('P', 'P'), ('R', 'R'), ('C', 'C'), ('X', 'X')], 'RET', help='Retiro')
    tde = fields.Boolean('TDE', help='Traslado desde otra EPS o EOC')
    tae = fields.Boolean('TAE', help='Traslado a otra EPS o EOC')
    tdp = fields.Boolean('TDP', help='Traslado desde otra administradora de pensiones')
    tap = fields.Boolean('TAP', help='Traslado a otra administradora de pensiones')
    vsp = fields.Boolean('VSP', help='Variacion permanente de salario')
    fixes = fields.Selection([('A', 'A'), ('C', 'C')], 'Correcciones')
    vst = fields.Boolean('VST', help='Variacion transitoria de salario')
    sln = fields.Boolean('SLN', help='Licencia no remunerada o suspension temporal del contrato')
    ige = fields.Boolean('IGE', help='Incapacidad general')
    lma = fields.Boolean('LMA', help='Licencia de maternidad o paternidad')
    vac = fields.Selection([('X', 'X'), ('L', 'L')], 'VAC', help='Vacaciones/LR')
    avp = fields.Boolean('AVP', help='Aporte voluntario de pension')
    vct = fields.Boolean('VCT', help='Variacion de centros de trabajo')
    irl = fields.Float('IRL', help='Dias de incapacidad por accidente de trabajo o enfermedad laboral')

    afp_code = fields.Char('Codigo AFP')
    afp_to_code = fields.Char('Codigo AFP a la cual se traslada')
    eps_code = fields.Char('Codigo EPS')
    eps_to_code = fields.Char('Codigo EPS a la cual se traslada')
    ccf_code = fields.Char('Codigo CCF')

    pens_days = fields.Integer('Dias cotizados pension')
    eps_days = fields.Integer('Dias cotizados EPS')
    arl_days = fields.Integer('Dias cotizados ARL')
    ccf_days = fields.Integer('Dias cotizados CCF')

    wage = fields.Integer('Salario basico')
    int_wage = fields.Boolean('Salario integral')
    wage_type = fields.Selection(string='Tipo de salario', selection=TYPE_WAGE)

    pens_ibc = fields.Float('IBC pension')
    eps_ibc = fields.Float('IBC EPS')
    arl_ibc = fields.Float('IBC ARL')
    ccf_ibc = fields.Float('IBC CCF')
    global_ibc = fields.Float('IBC Global')

    pens_rate = fields.Float('Tarifa pension')
    pens_cot = fields.Float('Cotizacion pension')
    ap_vol_contributor = fields.Float('Aportes voluntarios del afiliado')
    ap_vol_company = fields.Float('Aportes voluntarios del aportante')
    pens_total = fields.Float('Aportes totales de pension')

    fsol = fields.Float('Aportes a fondo de solidaridad')
    fsub = fields.Float('Aportes a fondo de subsistencia')
    ret_cont_vol = fields.Float('Valor no retenido por aportes voluntarios')

    eps_rate = fields.Float('Tarifa EPS')
    eps_cot = fields.Float('Cotizacion EPS')
    ups = fields.Float('Total UPS')
    aus_auth = fields.Char('Numero de autorizacion de incapacidad')
    gd_amount = fields.Float('Valor de la incapacidad EG')
    mat_auth = fields.Char('Numero de autorizacion de licencia')
    mat_amount = fields.Float('Valor de licencia')

    arl_rate = fields.Float('Tarifa ARL')
    work_center = fields.Char('Centro de trabajo')
    arl_cot = fields.Float('Cotizacion ARL')

    ccf_rate = fields.Float('Tarifa CCF')
    ccf_cot = fields.Float('Cotizacion CCF')
    sena_rate = fields.Float('Tarifa SENA')
    sena_cot = fields.Float('Cotizacion SENA')
    icbf_rate = fields.Float('Tarifa ICBF')
    icbf_cot = fields.Float('Cotizacion ICBF')
    esap_rate = fields.Float('Tarifa ESAP')
    esap_cot = fields.Float('Cotizacion ESAP')
    men_rate = fields.Float('Tarifa MEN')
    men_cot = fields.Float('Cotizacion MEN')
    exonerated = fields.Boolean('Exonerado de aportes')

    arl_code = fields.Char('Codigo ARL')
    arl_risk = fields.Char('Clase de riesgo')
    k_start = fields.Date('Fecha de ingreso')
    k_end = fields.Date('Fecha de retiro')
    vsp_start = fields.Date('Fecha de inicio de VSP')

    sln_start = fields.Date('Inicio licencia no remunerada')
    sln_end = fields.Date('Fin licencia no remunerada')
    ige_start = fields.Date('Inicio incapacidad EG')
    ige_end = fields.Date('Fin incapacidad EG')
    lma_start = fields.Date('Inicio licencia maternidad')
    lma_end = fields.Date('Fin licencia maternidad')
    vac_start = fields.Date('Inicio vacaciones')
    vac_end = fields.Date('Fin vacaciones')
    vct_start = fields.Date('Inicio cambio centro de trabajo')
    vct_end = fields.Date('Fin cambio de centro de trabajo')
    atep_start = fields.Date('Inicio ATEP')
    atep_end = fields.Date('Fin ATEP')
    other_ibc = fields.Float('IBC otros parafiscales')
    w_hours = fields.Integer('Horas laboradas')


class HrContributionForm(models.Model):
    _name = 'hr.contribution.form'

    name = fields.Char('Nombre')
    period_id = fields.Many2one('payslip.period', 'Periodo', domain=[('schedule_pay', '=', 'monthly')])
    group_id = fields.Many2one('hr.contract.group', 'Grupo de contratos')
    form_type = fields.Selection(FORM_TYPES, 'Tipo de planilla', default='E')
    branch_code = fields.Char('Codigo de sucursal')
    presentation = fields.Char('Presentacion', size=1, default='U')
    contract_ids = fields.Many2many('hr.contract', 'pila_contract_rel', 'pila_id', 'contract_id')
    state = fields.Selection(FORM_STATES, 'Estado', default='draft')
    file = fields.Binary('Archivo plano', readonly=True)
    journal_id = fields.Many2one('account.journal', "Diario contable")
    move_id = fields.Many2one('account.move', 'Asiento')
    move_id_name = fields.Char('Move Name')
    form_line_ids = fields.One2many('hr.contribution.form.line', 'contribution_id', string='Detalle')
    error_log = fields.Text('Reporte de errores')

    @api.multi
    def fix_o_rights(self, rights,start_p,end_p,contract):
        """ Retorna el IBC basado en los ingresos por otros derechos del empleado """
        if rights <= 0:
            return 0
        query="""select HH.id, HH.absence_id, HHD.sequence, HHS.gi_b2, HHS.gi_b90, HHS.gi_b180, HHS.gi_a180, HHS.sub_wd, HHS.no_payable
                 from hr_holidays_days as HHD
                 inner join hr_holidays as HH
                     on HH.id = HHD.holiday_id
                 inner join hr_holidays_status as HHS
                     on HHS.id = HHD.holiday_status_id and HHS.active and (HHS.general_illness  or (sub_wd and no_payable))
                 where   HHD.contract_id = {contrato} and
                         HHD.name BETWEEN '{s_p}' and '{e_p}'""".format(
                     contrato=contract,
                     s_p = start_p,
                     e_p=end_p)
        holiday_days = orm.fetchall(self._cr, query)
        #Organizar cantidad de dias por rangos de descuento por enfermedad general o prorroga
        days_b2, days_b90, days_b180, days_a180, otros = [0,None],[0,None],[0,None],[0,None], 0 #[CantidadDias, Porcentaje]
        for day in holiday_days:
            leave_id = self.env['hr.holidays'].browse(day[0])
            if day[0] == day[1]:
                raise Warning("La ausencia {aus} no puede tener una prorroga a si misma, se sugire borrar y crear una nueva ausencia".format(aus=leave_id.name))
            if day[7] and day[8]:# Evalua primero si es ausencia que modifique el IBC
                otros += 1
            elif day[2] <= 2: #Evalua ausencias de tipo Enfermedad general
                days_b2[0] += 1
                if not days_b2[1]:
                    days_b2[1] = day[3]
                if days_b2[1] and days_b2[1] != day[3]:
                    raise Warning("La ausencia {aus} tiene <Porcentaje a reconocer por enfermedad de 1 y 2 dias> diferente a otras ausencias reportadas en el periodo de {P}, revisar ausencias del contrato con id = {C}".format(aus=leave_id.name,P=start_p[:-2],C=contract))
            elif 2 < day[2] <= 90:
                days_b90[0] += 1
                if not days_b90[1]:
                    days_b90[1] = day[4]
                if days_b90[1] and days_b90[1] != day[4]:
                    raise Warning("La ausencia {aus} tiene <Porcentaje a reconocer por enfermedad de 3 a 90 dias> diferente a otras ausencias reportadas en el periodo de {P}, revisar ausencias del contrato con id = {C}".format(aus=leave_id.name,P=start_p[:-2],C=contract))
            elif 90 < day[2] <= 180:
                days_b180[0] += 1
                if not days_b180[1]:
                    days_b180[1] = day[5]
                if days_b180[1] and days_b180[1] != day[5]:
                    raise Warning("La ausencia {aus} tiene <Porcentaje a reconocer por enfermedad de 91 a 180 dias> diferente a otras ausencias reportadas en el periodo de {P}, revisar ausencias del contrato con id = {C}".format(aus=leave_id.name,P=start_p[:-2],C=contract))
            else:
                days_a180[0] += 1
                if not days_a180[1]:
                    days_a180[1] = day[6]
                if days_a180[1] and days_a180[1] != day[6]:
                    raise Warning("La ausencia {aus} tiene <Porcentaje a reconocer por enfermedad de 181 días en adelante> diferente a otras ausencias reportadas en el periodo de {P}, revisar ausencias del contrato con id = {C}".format(aus=leave_id.name,P=start_p[:-2],C=contract))
        #---------------------Calcular el IBC
        #Calcular NumeroDias por Porcentaje
        DiasPorcentaje = [days_b2, days_b90, days_b180, days_a180]
        total = [0,0] #[DiasPorcentaje, DiasAusencias]
        for DP in DiasPorcentaje:
            if not DP[1]:
                continue
            total[0] += float(DP[0] * DP [1])/100
            total[1] += DP[0]
        #Calculo IBC  por otros derechos
        rights = float(rights * total[1])/ total[0] if total[0] and total[0] else rights
        rights += float(self.env['hr.contract'].browse(contract).wage)/30 * otros if otros > 0 else 0
        return rights

    @api.multi
    def compute_ibc(self, contract, month, main):
        sdt = month + '-01'
        edt = month + "-" + str(monthrange(int(month[0:4]), int(month[5:7]))[2])

        plp = self.env['hr.payslip']

        earnings = plp.get_interval_category('earnings', sdt, edt, contract=contract.id)#DEVENGADO
        o_salarial_earnings = plp.get_interval_category('o_salarial_earnings', sdt, edt, contract=contract.id)#OTROS DEVENGOS SALARIALES
        comp_earnings = plp.get_interval_category('comp_earnings', sdt, edt, contract=contract.id)#INGRESOS COMPLEMENTARIOS

        if main != 'main':
            orig_exc = ('VAC_PAG', 'VAC_LIQ', 'PRIMA', 'PRIMA_LIQ')
            o_rights = plp.get_interval_category('o_rights', sdt, edt, exclude=orig_exc, contract=contract.id)
            if o_rights:
                o_rights = self.fix_o_rights(o_rights[0][1], sdt, edt, contract.id)
            else:
                o_rights = 0
        else:
            o_rights = 0

        sal_earnings_itv = earnings + o_salarial_earnings + comp_earnings
        sal_earnings = sum([x[1] for x in sal_earnings_itv]) + o_rights

        o_earnings_itv = plp.get_interval_category('o_earnings', sdt, edt, contract=contract.id)
        o_earnings = sum([x[1] for x in o_earnings_itv])

        top40 = (sal_earnings + o_earnings) * 0.4
        if o_earnings > top40:
            amount = sal_earnings + o_earnings - top40
            sal_earnings += o_earnings - top40
        else:
            amount = sal_earnings

        if contract.type_id.type_class == 'int':
            amount = amount * 0.7
            sal_earnings = sal_earnings * 0.7
        e_v = self.env['variables.economicas']
        smmlv = e_v.getValue('SMMLV', sdt + " 05:00:00") or 0.0
        # TOP25
        if amount > 25 * smmlv:
            amount = 25 * smmlv

        days = self.get_wd(contract, month=month, main=main)[0]

        sal_days = plp.get_interval_concept_qty('BASICO', sdt, edt, contract=contract.id)
        if sal_days:
            sal_days = sal_days[0][2]
        else:
            sal_days = 0

        days_to_add = days - sal_days if days != sal_days else 0
        if main == 'main':
            if amount < contract.wage and contract.wage != 0:
                amount += contract.wage * days_to_add / 30
                sal_earnings += contract.wage * days_to_add / 30
        return [amount, days], sal_earnings

    @api.multi
    def get_wd(self, contract, period=False, month="", main=False):
        if period:
            start_period = period.start_period
            end_period = period.end_period
        else:
            start_period = month + "-01"
            max_day = monthrange(int(month[0:4]), int(month[5:7]))[2]
            end_period = month + "-" + str(max_day)

        # Amarre a 30 dias o menos e ignorar incapacidades de dia 31
        max_day = int(end_period[8:10])
        max_day = 30 if max_day > 30 else max_day

        end_period = end_period[0:7] + "-" + str(max_day)

        ld_query = ("SELECT hhd.name, hhd.holiday_id, hhs.code, hhd.sequence "
                    "FROM hr_holidays_days hhd "
                    "INNER JOIN hr_holidays_status hhs ON hhs.id = hhd.holiday_status_id "
                    "WHERE hhd.name BETWEEN '{sd}' AND '{ed}' "
                    "AND hhd.contract_id = {k} "
                    "AND hhd.state in ('paid','validate') ".format(
                        sd=start_period, ed=end_period, k=contract.id))
                    #Se debe mantener esto el estado en 'paid' y 'validate'
                    #Si un empleado se incapacida despues de causar la nomina
                    #Se debe pagar la autoliquidacion a lo real
        ld_data = orm.fetchall(self._cr, ld_query)

        year = int(end_period[:4])
        month = int(end_period[5:7])
        end_day_month = calendar.monthrange(year,month)[1]
        day31 = end_day_month == 31

        if day31:
            query_day31 = """   select HHD.holiday_id
                                from hr_holidays_days as HHD
                                inner join hr_holidays_status as HHS
                                    on HHS.id = HHD.holiday_status_id
                                where HHD.contract_id = {contrato}
                                    and HHD.state in ('paid', 'validate')
                                    and HHD.name = '{day31}' """.format(
                                        contrato=contract.id,
                                        day31=end_period[:-2] + '31')
            day31 = orm.fetchall(self._cr, query_day31)

        # Agrupacion por ausencia
        leaves, total_leaves = {}, 0
        for ld in ld_data:
            if ld[1] not in leaves:
                leaves[ld[1]] = [1, ld[2], ld[3], ld[3]]
            else:
                leaves[ld[1]][0] += 1
                leaves[ld[1]][2] = ld[3] if leaves[ld[1]][2] > ld[3] else leaves[ld[1]][2]
                leaves[ld[1]][3] = ld[3] if leaves[ld[1]][3] < ld[3] else leaves[ld[1]][3]

            total_leaves += 1

        if total_leaves > 30:
            total_leaves = 30

        w102 = 30 - total_leaves if main == 'main' else 30

        # Date format
        dt_sp = datetime.strptime(start_period, DSDF).date()
        dt_ep = datetime.strptime(end_period, DSDF).date()
        dt_ksd = datetime.strptime(contract.date_start, DSDF).date()
        dt_ked = datetime.strptime(contract.date_end, DSDF).date() if contract.date_end else False
        # Calculo de decuccion de contrato por inicio o fin
        ded_start_days, ded_end_days = 0, 0
        if dt_ksd > dt_sp:
            if dt_ep >= dt_ksd:
                ded_start_days = (dt_ksd - dt_sp).days
            else:
                ded_start_days = 30

        if dt_ked and dt_ked <= dt_ep:
            ded_end_days = (dt_ep - dt_ked).days
            if dt_ep.day == 31 and ded_end_days:
                ded_end_days -= 1
            if dt_ked.month == 2:# Q hacer cuando el empeado se liquida el 28 o 29 de FEB
                ded_end_days += 2 if end_day_month == 28 else 1

        w102 -= ded_start_days
        w102 -= ded_end_days

        w102 = 0 if w102 < 0 else w102

        return w102, leaves, day31

    @api.multi
    def calculate_pila(self):
        self.get_contract_repeated()
        error_log = ""
        self._cr.execute("DELETE FROM hr_contribution_form_line where contribution_id = %s" % self.id)
        emp_lsq = ("SELECT hc.employee_id, hc.id FROM pila_contract_rel rel "
                   "INNER JOIN hr_contract hc ON rel.contract_id = hc.id "
                   "WHERE rel.pila_id = {pila} "
                   "GROUP BY hc.employee_id, hc.id "
                   "ORDER BY hc.employee_id asc, hc.id asc".format(pila=self.id))
        emp_ls = orm.fetchall(self._cr, emp_lsq)
        payslip_obj = self.env['hr.payslip']
        start_period = self.period_id.start_period
        end_period = self.period_id.end_period

        i, j = 0, len(emp_ls)
        bar = orm.progress_bar(i, j)
        lines = []
        e_v = self.env['variables.economicas']
        smmlv = e_v.getValue('SMMLV', end_period) or 0.0

        for emp in emp_ls:
            contract_id = self.env['hr.contract'].browse(emp[1])
            cot_type = prep_field(contract_id.fiscal_type_id.code, size=2)
            subcot_type = prep_field(contract_id.fiscal_subtype_id.code or '00', size=2)
            retired = True if contract_id.fiscal_subtype_id.code not in ['00', False] \
                              or contract_id.fiscal_type_id.code in ('12', '19') else False

            apr = contract_id.fiscal_type_id.code in ('12', '19')
            apr_lect = contract_id.fiscal_type_id.code == '12'

            # Consolidacion de dias de ausencia pagas del contrato en el periodo definido
            w102, leaves, day31 = self.get_wd(contract_id, period=self.period_id, main='main')

            # Generacion de lineas
            fl = []
            if w102:
                fl.append(['main', w102, 'WORK102', 0, 0])
            fl += [[k,
                    leaves[k][0] if leaves[k][0] <= 30 else 30,
                    leaves[k][1],
                    leaves[k][2],
                    leaves[k][3]]
                   for k in leaves]

            total_days = sum([x[1] for x in fl])
            if total_days > 30:
                error_log += "Hay mas de 30 dias reportados en contrato {k} \n".format(k=contract_id.name)


            # Asignacion de IBC GLOBAL en lineas
            # ref_wage = contract_id.wage if contract_id.wage >= smmlv else smmlv
            ref_wage = smmlv
            for line in fl:
                if line[0] == 'main':
                    current_comp_ibc, total_ingreso = self.compute_ibc(contract_id, self.period_id.start_period[0:7], line[0])
                    line_ibc = current_comp_ibc[0]
                else:
                    leave_id = self.env['hr.holidays'].browse(line[0])
                    line_ibc, total_ingreso = 0, 0
                    if leave_id.holiday_status_id.general_illness:
                        #{code_concept: [start,end, vaue]}
                        concepts_to_eval = {'EG_B2':[1,2,0], 'EG_B90':[3,90,0], 'EG_B180':[91,180,0],'EG_A180':[181,-1,0]}
                        leave_days_ids = filter(lambda z: start_period <= z.name <= end_period, leave_id.line_ids)
                        for cte in concepts_to_eval:
                            gis = payslip_obj.get_interval_concept_qty(cte, start_period, end_period, contract_id.id)
                            leave_total, leave_qty = 0, 0
                            for gi in gis:
                                leave_total += gi[1] if gi[1] else 0
                                leave_qty += gi[2] if gi[2] else 0
                            unit_value = leave_total / leave_qty if leave_qty else 0
                            concepts_to_eval[cte][2] = unit_value
                        for leave_day in leave_days_ids:
                            if not leave_day.days_payslip:
                                continue
                            for dc in concepts_to_eval.values():
                                if dc[2] and dc[0] <= leave_day.sequence <= (dc[1] if dc[1] > 0 else leave_day.sequence):
                                    line_ibc += dc[2]
                                    total_ingreso += dc[2]
                    elif leave_id.holiday_status_id.maternal_lic:
                        ml = payslip_obj.get_interval_concept_qty('MAT_LIC', start_period, end_period, contract_id.id)
                        line_ibc = total_ingreso = sum([x[1] for x in ml])
                    elif leave_id.holiday_status_id.paternal_lic:
                        pl = payslip_obj.get_interval_concept_qty('PAT_LIC', start_period, end_period, contract_id.id)
                        line_ibc = total_ingreso = sum([x[1] for x in pl])
                    elif leave_id.holiday_status_id.atep:
                        atep = payslip_obj.get_interval_concept_qty('ATEP', start_period, end_period, contract_id.id)
                        atep_p2 = payslip_obj.get_interval_concept_qty('ATEP_P2', start_period, end_period, contract_id.id)
                        line_ibc = total_ingreso = sum([x[1] for x in atep + atep_p2])
                    else:
                        ref_date = datetime.strptime(leave_id.date_from[0:10], "%Y-%m-%d") - relativedelta(months=1)
                        month = datetime.strftime(ref_date, "%Y-%m")
                        leave_ibc, total_ingreso = self.compute_ibc(contract_id, month, line[0])
                        if leave_ibc[0] == 0 or leave_ibc[1] == 0:
                            line_ibc = total_ingreso = contract_id.wage * line[1] / 30
                        else:
                            line_ibc = leave_ibc[0] * line[1] / leave_ibc[1]
                line.append(line_ibc)
                line.append(total_ingreso) if total_ingreso else line.append(line_ibc)

            total_ibc = sum([x[5] for x in fl])
            ingreso =  start_period <= contract_id.date_start <= end_period
            retiro = (start_period <= contract_id.date_end <= end_period) and contract_id.state == 'done'
            #Ajuste de tope minimo por linea, donde la sumatoria de lineas no debe ser menor a un SMMLV
            if total_ibc < smmlv and not (retiro or ingreso):
                for x in fl:
                    x[5] = float(smmlv * x[1])/30
                    x[6] = float(smmlv * x[1])/30
            #Ajuste de tope maximo por linea, donde la sumatoria de lineas no debe ser mayor a 25 SMMLV
            for x in fl:
                    x.append(x[5])
                    x.append(x[6])
            if total_ibc > smmlv * 25:
                for x in fl:
                    x[5] = (smmlv * 25 * x[1])/30
                    x[6] = (smmlv * 25 * x[1])/30
            total_ibc = sum([x[5] for x in fl])

            if total_days and total_ibc * 30 / total_days < ref_wage and not contract_id.type_id.type_class == 'int':
                ibc_to_adj = ref_wage * total_days / 30 - total_ibc
            else:
                ibc_to_adj = 0

            if ibc_to_adj:
                fl[0][5] += ibc_to_adj

            # ITERACION PRINCIPAL----
            pay_vac_comp = True
            apply_ret = True
            wage_type_main_line = False
            for line in fl:
                if isinstance(line[0], basestring) and line[0] == 'main':
                    leave_id = False
                    main = True
                else:
                    leave_id = self.env['hr.holidays'].browse(line[0])
                    leave_type = leave_id.holiday_status_id
                    lstart = leave_id.date_from[0:10]
                    if lstart < start_period:
                        lstart = start_period
                    lend = max([x.name for x in leave_id.line_ids])
                    if lend > end_period:
                        lend = end_period

                    main = False

                # Novedad de ingreso
                ing = "X" if start_period <= contract_id.date_start <= end_period and main else ''

                # Novedad de retiro
                wm = fl[0][0] == 'main'

                ret = (start_period <= contract_id.date_end <= end_period) and contract_id.state == 'done'#((main and wm) or (not main and leave_type.vacaciones))
                ret = ret and apply_ret
                ret = 'X' if ret else ''
                apply_ret = False

                # Variacion salario permanente
                wage_change_q = ("SELECT id, date "
                                 "FROM hr_contract_salary_change "
                                 "WHERE contract_id = {c} "
                                 "AND date BETWEEN '{df}' AND '{dt}'".format(
                    c=contract_id.id, df=start_period, dt=end_period))
                wage_change = orm.fetchall(self._cr, wage_change_q)
                vsp = False
                if wage_change:
                    for wc in wage_change:
                        if not ing:
                            vsp = True and main
                            vsp_date = wc[1]

                # Variacion transitoria de salario
                is_itv = payslip_obj.get_interval_category('earnings', start_period, end_period,
                                                           exclude=('BASICO',),
                                                           contract=contract_id.id)
                comp_itv = payslip_obj.get_interval_category('comp_earnings', start_period, end_period,
                                                             contract=contract_id.id)
                os_itv = payslip_obj.get_interval_category('o_salarial_earnings', start_period, end_period,
                                                           contract=contract_id.id)
                devibc = line[5] * 30 / line[1] > contract_id.wage

                if ((is_itv or comp_itv or os_itv or devibc) and main and not cot_type in ('12', '19')) or contract_id.part_time:
                    vst = True
                else:
                    vst = False

                # Indicador de licencia no remunerada
                sln = not main and leave_type.no_payable

                # Indicador novedad por incapacidad eg
                ige = not main and not sln and leave_type.general_illness

                # Indicador novedad por licencia de maternidad o paternidad
                lma = not main and (leave_type.maternal_lic or leave_type.paternal_lic) and not sln

                # Indicador por vacaciones
                vac = 'X' if not main and leave_type.vacaciones and not sln \
                    else 'L' if not main and not leave_type.vacaciones \
                                and not (leave_type.maternal_lic or leave_type.paternal_lic) \
                                and not leave_type.general_illness and not leave_type.atep and not sln else ''

                # Indicador aporte voluntario pension
                avp_itv = payslip_obj.get_interval_avp(start_period, end_period, contract=contract_id.id)
                if avp_itv and not retired:
                    avp = True
                else:
                    avp = False

                # Dias de incapacidad ATEP
                if not main and leave_type.atep and not sln:
                    irl = leaves[line[0]][0]
                else:
                    irl = 0

                # Codigos administradoras
                afp_code = contract_id.pensiones.codigo_afp if not retired else False
                eps_code = contract_id.eps.codigo_eps
                ccf_code = contract_id.cajacomp.codigo_ccf if not apr else False

                # Validacion de ciudad de caja y ciudad de desempeño contrato
                if contract_id.cajacomp and contract_id.cajacomp.city_id.provincia_id != contract_id.cuidad_desempeno.provincia_id:
                    error_log += u"La caja asignada en el contrato {k} " \
                                 u"no corresponde al departamento de desempeño \n".format(k=contract_id.name)

                # Dias de pension, siempre van full excepto si esta pensionado
                pens_days = line[1] if not retired else 0

                # Dias de EPS, ARL y CCF siempre van full excepto caja en aprendices
                eps_days = line[1]
                arl_days = line[1] if not (cot_type in ('12') and subcot_type in ('00')) else 0
                ccf_days = line[1] if not apr else 0
                # Salario
                wage_actual_q = ("SELECT id, date "
                                 "FROM hr_contract_salary_change "
                                 "WHERE contract_id = {c} "
                                 "AND date >= '{dt}'".format(
                                    c=contract_id.id, dt=end_period))
                wage_actual = orm.fetchall(self._cr, wage_actual_q)
                if not wage_actual:
                    wage = contract_id.wage if contract_id.wage >= smmlv else smmlv
                else:
                    wages = contract_id.wage_historic_ids.sorted(key=lambda r: r.date, reverse=True)
                    if len(wages) > 1:
                        wage = wages[-2].wage

                int_wage = contract_id.type_id.type_class == 'int'

                #Resolucion 454
                if not main and wage_type_main_line:
                    wage_type = wage_type_main_line
                elif int_wage:
                    wage_type = 'X'
                elif vst:
                    wage_type = 'V'
                elif apr:
                    wage_type = ' '
                else:
                    wage_type = 'F'

                if not wage_type_main_line:
                    wage_type_main_line = wage_type

                # IBC
                if (cot_type == '01' and subcot_type in ('01', '03', '06', '04')) or \
                        (cot_type in ('12', '19') and subcot_type in ('00')):
                    pens_ibc = 0
                else:
                    pens_ibc = rp1(25 * smmlv if line[5] > 25 * smmlv else line[5])
                eps_ibc = rp1(25 * smmlv if line[5] > 25 * smmlv else line[5])

                if line[0] != 'main':
                    pens_ibc = rp1(25 * smmlv if line[5] > 25 * smmlv else line[5])
                    eps_ibc = rp1(25 * smmlv if line[5] > 25 * smmlv else line[5])

                arl_ibc = rp1(line[5]) if not (cot_type in ('12') and subcot_type in ('00')) else 0
                arl_ibc = rp1(arl_ibc if arl_ibc <= 25 * smmlv else 25 * smmlv)


                vac_pag = payslip_obj.get_interval_concept('VAC_PAG', start_period, end_period, contract_id.id)
                vac_disf_data = payslip_obj.get_interval_concept_qty('VAC_DISF', start_period, end_period, contract_id.id)

                vac_liq = payslip_obj.get_interval_concept('VAC_LIQ', start_period, end_period, contract_id.id)

                vac_money = sum([x[1] for x in vac_pag + vac_liq])

                vac_disf = 0 if not vac_disf_data else vac_disf_data[0][1] if vac_disf_data[0][1] else 0
                vac_dist_qty = 0 if not vac_disf_data else vac_disf_data[0][2] if vac_disf_data[0][2] else 0

                ccf_ibc = 0
                if main and not apr:
                    ccf_ibc = line[8]
                    if vac_money > 0:
                        ccf_ibc += vac_money
                        pay_vac_comp = False
                else:
                    if not apr:
                        leave_id = self.env['hr.holidays'].browse(line[0])
                        if leave_id.holiday_status_id.vacaciones:
                            if self.env.user.company_id.fragment_vac:
                                leave_days_ids = len(filter(lambda z: start_period <= z.name <= end_period, leave_id.line_ids))
                            else:
                                leave_days_ids = leave_id.number_of_days_in_payslip
                            ccf_ibc += (vac_disf * leave_days_ids / vac_dist_qty)  if vac_dist_qty else 0
                        elif leave_id.holiday_status_id.general_illness or leave_id.holiday_status_id.no_payable or leave_id.holiday_status_id.atep:
                            ccf_ibc = 0#Se pone para que no entre al else, como control de q configuren bien las ausencias
                        elif (leave_id.holiday_status_id.maternal_lic or leave_id.holiday_status_id.paternal_lic) and leave_id.holiday_status_id.ibc:
                            ccf_ibc += line[5]
                        else:
                            ccf_ibc += float(line[8]*line[1])/30
                        #Intenta arreglar el problema de las vacaciones liquidadas negativas
                        #Se debe poner en cero si definitivamente no hay como compensarlo
                        #Se debe intentar pagar con otras vacaciones disfrutadas
                        if pay_vac_comp and (ccf_ibc + vac_money) > 0:
                            ccf_ibc += vac_money
                            pay_vac_comp = False
                    else:
                        ccf_ibc = 0
                ccf_ibc = rp1(ccf_ibc)

                global_ibc = total_ibc

                # Indicador de exonerabilidad
                exonerated = global_ibc < 10 * smmlv and not int_wage and not apr

                # IBC de otros parafiscales
                other_ibc = ccf_ibc if not exonerated else 0

                # Tarifa de pension van en cero solo si es pensionado y 12 si es no remunerasdo
                pens_rate = self.env.user.company_id.percentage_total/100
                if contract_id.high_risk:
                    pens_rate = 0.26
                if not main and leave_type.no_payable:
                    if contract_id.high_risk:
                        pens_rate = 0.22
                    else:
                        percentage = 3.0 if self.env.user.company_id.percentage_total == 3.0 else self.env.user.company_id.percentage_employer
                        pens_rate = percentage/100
                pens_rate = pens_rate if not retired and not apr else 0

                # Cotizacion de pension
                pens_cot = rp(pens_ibc * pens_rate)

                # Aporte voluntario
                if avp:
                    ap_vol_contributor = rp(sum([x[1] for x in avp_itv]) if not retired else 0)
                else:
                    ap_vol_contributor = 0

                # Total pensiones
                pens_total = rp(pens_cot + ap_vol_contributor)

                # Fondo de solidaridad
                fsol = rp(pens_ibc * 0.005 if global_ibc >= 4 * smmlv and not retired and not sln else 0)
                fsol = fsol if self.env.user.company_id.cal_fond_sol_sub else 0

                # Fondo de subsistencia
                fsrate = 0
                if global_ibc > 4 * smmlv:
                    fsrate += 0.005
                if 16 * smmlv <= global_ibc <= 17 * smmlv:
                    fsrate += 0.002
                elif 17 * smmlv <= global_ibc <= 18 * smmlv:
                    fsrate += 0.004
                elif 18 * smmlv <= global_ibc <= 19 * smmlv:
                    fsrate += 0.006
                elif 19 * smmlv <= global_ibc <= 20 * smmlv:
                    fsrate += 0.008
                elif global_ibc > 20 * smmlv:
                    fsrate += 0.01
                fsub = rp(pens_ibc * fsrate if not retired and not sln else 0)
                fsub = fsub if self.env.user.company_id.cal_fond_sol_sub else 0

                ret_cont_vol_itv = payslip_obj.get_interval_concept('RET_CTG_DIF_FVP', start_period, end_period,
                                                                    contract=contract_id.id)
                ret_cont_vol = sum([x[1] for x in ret_cont_vol_itv]) if avp else 0
                if ret_cont_vol < 0:
                    ret_cont_vol = 0

                # Tarifa EPS Todas pagan
                eps_rate = 0.04
                if global_ibc >= 10 * smmlv or int_wage or apr:
                    eps_rate = 0.125
                if not main and leave_type.no_payable:
                    eps_rate = 0

                # Cotizacion EPS
                eps_cot = rp(eps_ibc * eps_rate)

                # Autorizacion de incapacidad
                # aus_auth = line.no_incapacidad if not main and leave_type.general_illness else False
                aus_auth, mat_auth = False, False  # Campo exclusivo de aportes en linea.
                # mat_auth = line.no_incapacidad if not main and (leave_type.maternal_lic or leave_type.paternal_lic) \
                #     else False

                # Tarifa ARL
                arl_rate = contract_id.pct_arp / 100 if main and not apr_lect else 0

                # Cotizacion ARL
                arl_cot = rp(arl_ibc * arl_rate)

                work_center = contract_id.workcenter

                # Tarifa CCF
                if (main or (self.env.user.company_id.quote_rate_ibc_ccf_lics and (leave_type.paternal_lic or leave_type.maternal_lic)) or leave_type.vacaciones or (not main and ret == 'X')) and not apr and ccf_ibc:
                    ccf_rate = 0.04
                else:
                    ccf_rate = 0

                # Cotizacion CCF
                ccf_cot = rp(ccf_ibc * ccf_rate)

                # Tarifa SENA
                sena_rate = 0.02 if global_ibc >= 10 * smmlv or int_wage else 0
                if sln:
                    sena_rate = 0

                # Cotizacion SENA
                sena_cot = rp(other_ibc * sena_rate)

                # Tarifa ICBF
                icbf_rate = 0.03 if global_ibc >= 10 * smmlv or int_wage else 0
                if sln:
                    icbf_rate = 0

                # Cotizacion ICBF
                icbf_cot = rp(other_ibc * icbf_rate)

                # Codigo ARL
                arl_code = contract_id.arl.codigo_arl if not apr_lect else False

                # Riesgo ARL
                arl_risk = contract_id.riesgo.name if not apr_lect else False

                # Datos de contrato
                k_start = contract_id.date_start if ing else False
                k_end = contract_id.date_end if ret else False

                # Fechas de novedades
                vsp_start = vsp_date if vsp else False

                sln_start = lstart if not main and sln else False
                sln_end = lend if not main and sln else False

                ige_start = lstart if not main and ige else False
                ige_end = lend if not main and ige else False

                lma_start = lstart if not main and lma else False
                lma_end = lend if not main and lma else False

                vac_start = lstart if not main and vac else False
                vac_end = lend if not main and vac else False

                atep = leave_type.atep if not main else False
                atep_start = lstart if not main and atep else False
                atep_end = lend if not main and atep else False

                w_hours = line[1] * 8

                data = {
                    'contribution_id': self.id,
                    'employee_id': emp[0],
                    'contract_id': contract_id.id,
                    'leave_id': leave_id.id if leave_id else False,
                    'main': main,
                    'ing': ing,
                    'ret': ret,
                    'tde': False,  # TODO
                    'tae': False,  # TODO
                    'tdp': False,  # TODO
                    'tap': False,  # TODO
                    'vsp': vsp,
                    'fixes': False,  # TODO
                    'vst': vst,
                    'sln': sln,
                    'ige': ige,
                    'lma': lma,
                    'vac': vac,
                    'avp': avp,
                    'vct': False,  # TODO
                    'irl': irl,
                    'afp_code': afp_code,
                    'afp_to_code': False,  # TODO
                    'eps_code': eps_code,
                    'eps_to_code': False,  # TODO
                    'ccf_code': ccf_code,
                    'pens_days': pens_days,
                    'eps_days': eps_days,
                    'arl_days': arl_days,
                    'ccf_days': ccf_days,
                    'wage': wage,
                    'int_wage': int_wage,
                    'pens_ibc': pens_ibc,
                    'eps_ibc': eps_ibc,
                    'arl_ibc': arl_ibc,
                    'ccf_ibc': ccf_ibc,
                    'global_ibc': global_ibc,
                    'pens_rate': pens_rate,
                    'pens_cot': pens_cot,
                    'ap_vol_contributor': ap_vol_contributor,
                    'ap_vol_company': 0,  # TODO
                    'pens_total': pens_total,
                    'fsol': fsol,
                    'fsub': fsub,
                    'ret_cont_vol': ret_cont_vol,
                    'eps_rate': eps_rate,
                    'eps_cot': eps_cot,
                    'ups': 0,  # TODO
                    'aus_auth': aus_auth,
                    'gd_amohnt': False,  # TODO
                    'mat_auth': mat_auth,
                    'arl_rate': arl_rate,
                    'work_center': work_center,
                    'arl_cot': arl_cot,
                    'ccf_rate': ccf_rate,
                    'ccf_cot': ccf_cot,
                    'sena_rate': sena_rate,
                    'sena_cot': sena_cot,
                    'icbf_rate': icbf_rate,
                    'icbf_cot': icbf_cot,
                    'esap_rate': 0,  # TODO
                    'esap_cot': 0,  # TODO
                    'men_rate': 0,  # TODO
                    'men_cot': 0,  # TODO
                    'exonerated': exonerated,
                    'arl_code': arl_code,
                    'arl_risk': arl_risk,
                    'k_start': k_start,
                    'k_end': k_end,
                    'vsp_start': vsp_start,
                    'sln_start': sln_start,
                    'sln_end': sln_end,
                    'ige_start': ige_start,
                    'ige_end': ige_end,
                    'lma_start': lma_start,
                    'lma_end': lma_end,
                    'vac_start': vac_start,
                    'vac_end': vac_end,
                    'vct_start': False,  # TODO
                    'vct_end': False,  # TODO
                    'atep_start': atep_start,
                    'atep_end': atep_end,
                    'other_ibc': other_ibc,
                    'w_hours': w_hours,
                    'wage_type':wage_type,
                }
                lines.append(data)

            i += 1
            bar = orm.progress_bar(i, j, bar, emp[0])
        orm.direct_create(self._cr, self._uid, 'hr_contribution_form_line', lines)
        self.error_log = error_log

    @api.multi
    def generate_pila(self):
        total_text = ''
        break_line = '\r\n'
        # ----- HEADER ----- #
        hl = [''] * (22 + 1)
        # 1: Tipo de registro
        hl[1] = '01'

        # 2: Modalidad de la planilla
        hl[2] = '1'

        # 3: Secuencia # TODO Está generando el 0001 pero se debe validar que siempre sea el mismo
        hl[3] = '0001'

        # 4: Nombre o razon social del aportante
        hl[4] = prep_field(self.env.user.company_id.partner_id.name, size=200)

        # 5: Tipo de documento del aportante # TODO Asignado directamente tipo de documento NIT
        hl[5] = 'NI'

        # 6: Numero de identificacion del aportante
        hl[6] = prep_field(self.env.user.company_id.partner_id.ref, size=16)

        # 7: Digito de verificacion
        hl[7] = str(self.env.user.company_id.partner_id.dev_ref)

        # 8: Tipo de planilla
        hl[8] = self.form_type

        # 9: Numero de la planilla asociada a esta planilla # TODO revisar casos de planillas N y F
        if self.form_type in ['E']:
            hl[9] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 10: Fecha de planilla de pago asociada a esta planilla
        if self.form_type not in ['N', 'F']:
            hl[10] = prep_field(" ", size=10)
        else:
            raise Warning("Tipo de planilla no soportada temporalmente")

        # 11: Forma de presentacion # TODO temporalmente forma de presentacion unica
        hl[11] = prep_field(self.presentation, size=1)

        # 12: Codigo de sucursal # TODO referente campo 11
        hl[12] = prep_field(self.branch_code, size=10)

        # 13: Nombre de la sucursal
        hl[13] = prep_field(self.branch_code, size=40)

        # 14: Código de la ARL a la cual el aportante se encuentra afiliado

        hl[14] = prep_field(self.env.user.company_id.arl_id.codigo_arl, size=6)

        # 15: Período de pago para los sistemas diferentes al de salud
        hl[15] = prep_field(self.period_id.start_period[0:7], size=7)

        # 16: Período de pago para el sistema de salud.
        pay_ref_date = datetime.strptime(self.period_id.start_period, "%Y-%m-%d") + relativedelta(months=1)
        pay_month = datetime.strftime(pay_ref_date, "%Y-%m")
        hl[16] = prep_field(pay_month, size=7)

        # 17: Número de radicación o de la Planilla Integrada de Liquidación de Aportes. (Asignado por el sistema)
        hl[17] = prep_field(" ", size=10)

        # 18: Fecha de pago (aaaa-mm-dd) (Asignado por el siustema)
        hl[18] = prep_field(" ", size=10)

        # 19: Numero total de empleados
        emp_count_q = ("SELECT count(hc.employee_id) FROM pila_contract_rel rel "
                       "INNER JOIN hr_contract hc on hc.id = rel.contract_id "
                       "INNER JOIN hr_employee he on he.id = hc.employee_id "
                       "WHERE rel.pila_id = {pila} "
                       "GROUP by hc.employee_id".format(pila=self.id))
        emp_count = orm.fetchall(self._cr, emp_count_q)
        hl[19] = prep_field(len(emp_count), align='right', fill='0', size=5)

        # 20: Valor total de la nomina
        ibp_sum = sum([x.ccf_ibc for x in self.form_line_ids])
        hl[20] = prep_field(int(ibp_sum), align='right', fill='0', size=12)

        # 21: Tipo de aportante
        hl[21] = prep_field("1", size=2)

        # 22: Codigo de operador de informacion
        hl[22] = prep_field(" ", size=2)

        for x in hl:
            total_text += x
        total_text += break_line

        # ----- BODY ----- #
        i, j = 0, len(self.form_line_ids)
        bar = orm.progress_bar(i, j)
        seq = 0
        for l in self.form_line_ids:
            seq += 1
            employee = l.employee_id
            ref_type = employee.partner_id.ref_type.code
            bl = [''] * (98 + 1)
            # 1: Tipo de registro
            bl[1] = '02'
            # 2: Secuencia
            bl[2] = prep_field(seq, align='right', fill='0', size=5)
            # 3: Tipo de documento de cotizante
            bl[3] = prep_field(ref_type, size=2)
            # 4: Numero de identificacion cotizante
            bl[4] = prep_field(employee.partner_id.ref, size=16)
            # 5: Tipo de cotizante
            bl[5] = prep_field(l.contract_id.fiscal_type_id.code if l.contract_id.fiscal_type_id.code != '51' else '01',
                               size=2)
            # 6: Subtipo de cotizante
            bl[6] = prep_field(l.contract_id.fiscal_subtype_id.code or '00', size=2)
            # 7: Extranjero no obligado a cotizar pensiones
            foreign = False
            # foreign = employee.partner_id.country_id.code != 'CO' and ref_type in ('CE', 'PA', 'CD')
            bl[7] = 'X' if foreign else ' '
            # 8: Colombiano en el exterior
            is_col = True if ref_type in ('CC', 'TI') and employee.partner_id.country_id.code == 'CO' else False
            in_ext = False
            if l.contract_id.cuidad_desempeno:
                in_ext = True if l.contract_id.cuidad_desempeno.provincia_id.country_id.code != 'CO' else False
            bl[8] = 'X' if is_col and in_ext else ' '
            # 9: Código del departamento de la ubicación laboral
            bl[9] = prep_field(l.contract_id.cuidad_desempeno.provincia_id.code, size=2)
            # 10: Código del municipio de ubicación laboral
            bl[10] = prep_field(l.contract_id.cuidad_desempeno.code, size=3)
            # 11: Primer apellido
            if employee.partner_id.primer_apellido:
                pap = strip_accents(employee.partner_id.primer_apellido.upper()).replace(".", "")
                bl[11] = prep_field(pap, size=20)
            else:
                bl[11] = prep_field(' ', size=20)
            # 12: Segundo apellido
            if employee.partner_id.segundo_apellido:
                sap = strip_accents(employee.partner_id.segundo_apellido.upper()).replace(".", "")
                bl[12] = prep_field(sap, size=30)
            else:
                bl[12] = prep_field(' ', size=30)
            # 13: Primer nombre
            if employee.partner_id.primer_nombre:
                pno = strip_accents(employee.partner_id.primer_nombre.upper()).replace(".", "")
                bl[13] = prep_field(pno, size=20)
            else:
                bl[13] = prep_field(' ', size=20)
            # 14: Segundo nombre
            if employee.partner_id.otros_nombres:
                sno = strip_accents(employee.partner_id.otros_nombres.upper()).replace(".", "")
                bl[14] = prep_field(sno, size=30)
            else:
                bl[14] = prep_field(' ', size=30)
            # 15: Ingreso
            bl[15] = 'X' if l.ing else ' '
            # 16: Retiro
            bl[16] = 'X' if l.ret else ' '
            # 17: Traslasdo desde otra eps
            bl[17] = 'X' if l.tde else ' '
            # 18: Traslasdo a otra eps
            bl[18] = 'X' if l.tae else ' '
            # 19: Traslasdo desde otra administradora de pensiones
            bl[19] = 'X' if l.tdp else ' '
            # 20: Traslasdo a otra administradora de pensiones
            bl[20] = 'X' if l.tap else ' '
            # 21: Variacion permanente del salario
            bl[21] = 'X' if l.vsp else ' '
            # 22: Correcciones
            bl[22] = 'X' if l.fixes else ' '
            # 23: Variacion transitoria del salario
            bl[23] = 'X' if l.vst else ' '
            # 24: Suspension temporal del contrato
            bl[24] = 'X' if l.sln else ' '
            # 25: Incapacidad temporal por enfermedad general
            bl[25] = 'X' if l.ige else ' '
            # 26: Licencia de maternidad o paternidad
            bl[26] = 'X' if l.lma else ' '
            # 27: Vacaciones, licencia remunerada
            bl[27] = l.vac if l.vac else ' '
            # 28: Aporte voluntario
            bl[28] = 'X' if l.avp else ' '
            # 29: Variacion de centro de trabajo
            bl[29] = 'X' if l.vct else ' '
            # 30: Dias de incapacidad por enfermedad laboral
            bl[30] = prep_field("{:02.0f}".format(l.irl), align='right', fill='0', size=2)
            # 31: Codigo de la administradora de fondos de pensiones
            bl[31] = prep_field(l.afp_code, size=6)
            # 32: Codigo de administradora de pensiones a la cual se traslada el afiliado #TODO
            bl[32] = prep_field(l.afp_to_code, size=6)
            # 33: Codigo de EPS a la cual pertenece el afiliado
            bl[33] = prep_field(l.eps_code, size=6)
            # 34: Codigo de eps a la cual se traslada el afiliado
            bl[34] = prep_field(l.eps_to_code, size=6)
            # 35: Código CCF a la cual pertenece el afiliado
            bl[35] = prep_field(l.ccf_code, size=6)
            # 36: Numero de dias cotizados a pension
            bl[36] = prep_field("{:02.0f}".format(l.pens_days), align='right', fill='0', size=2)
            # 37: Numero de dias cotizados a salud
            bl[37] = prep_field("{:02.0f}".format(l.eps_days), align='right', fill='0', size=2)
            # 38: Numero de dias cotizados a ARL
            bl[38] = prep_field("{:02.0f}".format(l.arl_days), align='right', fill='0', size=2)
            # 39: Numero de dias cotizados a CCF
            bl[39] = prep_field("{:02.0f}".format(l.ccf_days), align='right', fill='0', size=2)
            # 40: Salario basico
            bl[40] = prep_field("{:09.0f}".format(l.wage), align='right', fill='0', size=9)
            # 41: Salario integral, resolucion 454
            bl[41] = l.wage_type
            # 42: IBC pension
            bl[42] = prep_field("{:09.0f}".format(l.pens_ibc), align='right', fill='0', size=9)
            # 43: IBC salud
            bl[43] = prep_field("{:09.0f}".format(l.eps_ibc), align='right', fill='0', size=9)
            # 44: IBC arl
            bl[44] = prep_field("{:09.0f}".format(l.arl_ibc), align='right', fill='0', size=9)
            # 45: IBC CCF
            bl[45] = prep_field("{:09.0f}".format(l.ccf_ibc), align='right', fill='0', size=9)
            # 46: Tarifa de aporte a pensiones
            bl[46] = prep_field("{:01.5f}".format(l.pens_rate), align='right', fill='0', size=7)
            # 47: Cotizacion pension
            bl[47] = prep_field("{:09.0f}".format(l.pens_cot), align='right', fill='0', size=9)
            # 48: Aportes voluntarios del afiliado
            bl[48] = prep_field("{:09.0f}".format(l.ap_vol_contributor), align='right', fill='0', size=9)
            # 49: Aportes voluntarios del aportante
            bl[49] = prep_field("{:09.0f}".format(l.ap_vol_company), align='right', fill='0', size=9)
            # 50: Total cotizacion pensiones
            bl[50] = prep_field("{:09.0f}".format(l.pens_total), align='right', fill='0', size=9)
            # 51: Aportes a fondo solidaridad
            bl[51] = prep_field("{:09.0f}".format(l.fsol), align='right', fill='0', size=9)
            # 52: Aportes a fondo subsistencia
            bl[52] = prep_field("{:09.0f}".format(l.fsub), align='right', fill='0', size=9)
            # 53: Valor no retenido por aportes voluntarios
            bl[53] = prep_field("{:09.0f}".format(l.ret_cont_vol), align='right', fill='0', size=9)
            # 54: Tarifa de aportes salud
            bl[54] = prep_field("{:01.5f}".format(l.eps_rate), align='right', fill='0', size=7)
            # 55: Aportes salud
            bl[55] = prep_field("{:09.0f}".format(l.eps_cot), align='right', fill='0', size=9)
            # 56: Total UPS adicional
            bl[56] = prep_field("{:09.0f}".format(l.ups), align='right', fill='0', size=9)
            # 57: Numero de autorizacion de incapacidad
            bl[57] = prep_field(l.aus_auth, size=15)
            # 58: Valor de la incapacidad por enf general
            bl[58] = prep_field("{:09.0f}".format(l.gd_amount), align='right', fill='0', size=9)
            # 59: Numero de autorizacion por licencia de maternidad
            bl[59] = prep_field(l.mat_auth, size=15)
            # 60: Valor de licencia de maternidad
            bl[60] = prep_field("{:09.0f}".format(l.mat_amount), align='right', fill='0', size=9)
            # 61: Tarifa de aportes a riesgos laborales
            bl[61] = prep_field("{:01.5f}".format(l.arl_rate), align='right', fill='0', size=9)
            # 62: Centro de trabajo
            bl[62] = prep_field(l.work_center, align='right', fill='0', size=9)
            # 63: Cotizacion obligatoria a riesgos laborales
            bl[63] = prep_field("{:09.0f}".format(l.arl_cot), align='right', fill='0', size=9)
            # 64: Tarifa de aportes CCF
            bl[64] = prep_field("{:01.5f}".format(l.ccf_rate), align='right', fill='0', size=7)
            # 65: Aportes CCF
            bl[65] = prep_field("{:09.0f}".format(l.ccf_cot), align='right', fill='0', size=9)
            # 66: Tarifa SENA
            bl[66] = prep_field("{:01.5f}".format(l.sena_rate), align='right', fill='0', size=7)
            # 67: Aportes SENA
            bl[67] = prep_field("{:09.0f}".format(l.sena_cot), align='right', fill='0', size=9)
            # 68: Tarifa ICBF
            bl[68] = prep_field("{:01.5f}".format(l.icbf_rate), align='right', fill='0', size=7)
            # 69: Aportes ICBF
            bl[69] = prep_field("{:09.0f}".format(l.icbf_cot), align='right', fill='0', size=9)
            # 70: Tarifa ESAP
            bl[70] = prep_field("{:01.5f}".format(l.esap_rate), align='right', fill='0', size=7)
            # 71: Aportes ESAP
            bl[71] = prep_field("{:09.0f}".format(l.esap_cot), align='right', fill='0', size=9)
            # 72: Tarifa MEN
            bl[72] = prep_field("{:01.5f}".format(l.men_rate), align='right', fill='0', size=7)
            # 73: Aportes MEN
            bl[73] = prep_field("{:09.0f}".format(l.men_cot), align='right', fill='0', size=9)
            # 74: Tipo de documento del cotizante principal
            bl[74] = prep_field(' ', size=2)
            # 75: Numero de documento de cotizante principal
            bl[75] = prep_field(' ', size=16)
            # 76: Exonerado de aportes a paraficales y salud
            bl[76] = 'S' if l.exonerated else 'N'
            # 77: Codigo de la administradora de riesgos laborales
            bl[77] = prep_field(l.arl_code, size=6)
            # 78: Clase de riesgo en la cual se encuentra el afiliado
            bl[78] = prep_field(l.arl_risk, size=1)
            # 79: Indicador de tarifa especial de pensiones
            bl[79] = prep_field(' ', size=1)
            # 80: Fecha de ingreso
            bl[80] = prep_field(l.k_start, size=10)
            # 81: Fecha de retiro
            bl[81] = prep_field(l.k_end, size=10)
            # 82: Fecha de inicio de VSP
            bl[82] = prep_field(l.vsp_start, size=10)
            # 83: Fecha de inicio SLN
            bl[83] = prep_field(l.sln_start, size=10)
            # 84: Fecha de fin SLN
            bl[84] = prep_field(l.sln_end, size=10)
            # 85: Fecha de inicio IGE
            bl[85] = prep_field(l.ige_start, size=10)
            # 86: Fecha de fin IGE
            bl[86] = prep_field(l.ige_end, size=10)
            # 87: Fecha de inicio LMA
            bl[87] = prep_field(l.lma_start, size=10)
            # 88: Fecha de fin LMA
            bl[88] = prep_field(l.lma_end, size=10)
            # 89: Fecha de inicio VAC
            bl[89] = prep_field(l.vac_start, size=10)
            # 90: Fecha de fin VAC
            bl[90] = prep_field(l.vac_end, size=10)

            bl[91] = prep_field(l.vct_start, size=10)
            bl[92] = prep_field(l.vct_end, size=10)
            # 93: Fecha de inicio ATEP
            bl[93] = prep_field(l.atep_start, size=10)
            # 94: Fecha de fin ATEP
            bl[94] = prep_field(l.atep_end, size=10)
            # 95: IBC otros parafiscales
            bl[95] = prep_field("{:09.0f}".format(l.other_ibc), align='right', fill='0', size=9)

            # 96: Numero de horas laboradas
            bl[96] = prep_field("{:03.0f}".format(l.w_hours), align='right', fill='0', size=3)

            bl[97] = prep_field('', size=10)

            i += 1
            bar = orm.progress_bar(i, j, bar)
            for x in bl:
                total_text += x
            total_text += break_line

            # decode and generate txt
        final_content = strip_accents(total_text.encode('utf-8', 'replace').decode('utf-8'))
        file_text = base64.b64encode(final_content)

        self.write({'file': file_text})

        return total_text

    @api.multi
    def load_contract(self):
        self._cr.execute("DELETE FROM pila_contract_rel where pila_id = %s" % self.id)
        if self.group_id:
            groupwh = " AND hc.group_id = {group} ".format(group=self.group_id.id)
        else:
            groupwh = " "
        active = """
        SELECT hc.id FROM hr_contract hc
        INNER JOIN hr_payslip hp ON hp.contract_id = hc.id
        WHERE hp.liquidacion_date BETWEEN '{date_from}' AND '{date_to}'
        {groupwh}
        and hc.id not in (
            select contract_id
            from pila_contract_rel
            where pila_id in (select id from hr_contribution_form where period_id = {periodo}) )
        GROUP BY hc.id""".format(date_from=self.period_id.start_period,
                                        date_to=self.period_id.end_period,
                                        groupwh=groupwh,
                                        periodo=self.period_id.id)
        ca = [x[0] for x in orm.fetchall(self._cr, active)]

        for contract in ca:
            self._cr.execute("INSERT into pila_contract_rel (pila_id, contract_id) VALUES ({pila}, {contract})".format(
                pila=self.id, contract=contract))
        return True

    @api.multi
    def load_pending(self):
        self._cr.execute("DELETE FROM pila_contract_rel where pila_id = %s" % self.id)
        if self.group_id:
            groupwh = " AND hc.group_id = {group} ".format(group=self.group_id.id)
        else:
            groupwh = " "

        calculated = ("SELECT hcfl.contract_id from hr_contribution_form_line hcfl "
                      "LEFT JOIN hr_contribution_form hcf on hcf.id = hcfl.contribution_id "
                      "WHERE hcf.period_id = {period} "
                      "group by hcfl.contract_id".format(period=self.period_id.id))
        clc = tuple([x[0] for x in orm.fetchall(self._cr, calculated)] + [0])


        active = ("SELECT hc.id FROM hr_contract hc "
                  "INNER JOIN hr_payslip hp ON hp.contract_id = hc.id "
                  "WHERE hp.liquidacion_date BETWEEN '{date_from}' AND '{date_to}' "
                  "AND hc.id not in {clc} "
                  "{groupwh} GROUP BY hc.id".format(date_from=self.period_id.start_period,
                                                    date_to=self.period_id.end_period,
                                                    clc=clc,
                                                    groupwh=groupwh))
        ca = [x[0] for x in orm.fetchall(self._cr, active)]

        for contract in ca:
            self._cr.execute("INSERT into pila_contract_rel (pila_id, contract_id) VALUES ({pila}, {contract})".format(
                pila=self.id, contract=contract))
        return True

    @api.multi
    def get_acc_type(self, contract_id):
        kt = contract_id.type_id
        acc = kt.type_class + "_" + kt.section[0:3]
        return acc

    @api.multi
    def draft_contform(self):
        self.state = 'draft'
        if self.move_id:
            account_move_line_sel ="""
            select id from account_move_line where move_id = {asiento}
            """.format(asiento=self.move_id.id)
            account_move_line = [x[0] for x in orm.fetchall(self._cr, account_move_line_sel)]
            if account_move_line:
                account_move_line_tuple = tuple(account_move_line if len(account_move_line) > 1 else [account_move_line[0],0])
                analytic_lines_sel = """
                select id from account_analytic_line where move_id in {moves}
                """.format(moves=account_move_line_tuple)
                analytic_lines = [x[0] for x in orm.fetchall(self._cr, analytic_lines_sel)]
                if analytic_lines:
                    orm.fast_delete(self._cr, 'account_analytic_line', ('id', analytic_lines))
                orm.fast_delete(self._cr, 'account_move_line', ('id', account_move_line))
            orm.fast_delete(self._cr, 'account_move', ('id', self.move_id.id))
            self._cr.execute('update hr_contribution_form set move_id = null where id = {pila}'.format(pila=self.id))

    @api.multi
    def close_contform(self):
        liquid_date = self.period_id.end_period
        start_date = self.period_id.start_period
        start_date_tmp = datetime.strftime(
                            datetime.strptime(start_date, "%Y-%m-%d") - relativedelta(months=1),
                            "%Y-%m-%d")
        account_period = self.env['account.period'].find(liquid_date)[0]
        po = self.env['hr.payslip']
        smmlv = self.env['variables.economicas'].getValue('SMMLV', liquid_date) or 0.0

        if not self.move_id_name:
            journal_seq = self.journal_id.sequence_id
            name = self.env['ir.sequence'].next_by_id(journal_seq.id)
            self.move_id_name = name
        else:
            name = self.move_id_name

        move_data = {
            'narration': "APORTES {p}".format(p=self.period_id.name),
            'date': liquid_date,
            'name': name,
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'period_id': account_period.id,
            'partner_id': self.env.user.company_id.partner_id.id,
            'state': 'posted'
        }

        move_id = orm.direct_create(self._cr, self._uid, 'account_move', [move_data], company=True)[0][0]
        self.move_id = self.env['account.move'].browse(move_id)

        p_query = ("SELECT contract_id, "
                   "sum(pens_total) + sum(fsol) + sum(fsub) - sum(ap_vol_contributor) - sum(ap_vol_company) as pens, sum(eps_cot) as eps, sum(arl_cot) as arl, "
                   "sum(ccf_cot) as ccf, sum(sena_cot) as sena, sum(icbf_cot) as icbf "
                   "from hr_contribution_form_line "
                   "WHERE contribution_id = {cont} "
                   "GROUP BY contract_id".format(cont=self.id))
        hcfl = orm.fetchall(self._cr, p_query)

        ap_template = {
            'reg_adm_debit': False, 'reg_com_debit': False, 'reg_ope_debit': False,
            'int_adm_debit': False, 'int_com_debit': False, 'int_ope_debit': False,
            'apr_adm_debit': False, 'apr_com_debit': False, 'apr_ope_debit': False,
            'reg_adm_credit': False, 'reg_com_credit': False, 'reg_ope_credit': False,
            'int_adm_credit': False, 'int_com_credit': False, 'int_ope_credit': False,
            'apr_adm_credit': False, 'apr_com_credit': False, 'apr_ope_credit': False,
            'partner_type': False,
        }

        ap_concepts = {'AP_PENS': ap_template.copy(),
                       'AP_EPS': ap_template.copy(),
                       'AP_ARL': ap_template.copy(),
                       'AP_CCF': ap_template.copy(),
                       'AP_SENA': ap_template.copy(),
                       'AP_ICBF': ap_template.copy()
                       }

        for apc in ap_concepts:
            concept_id = self.env['hr.concept'].search([('code', '=', apc)])
            if not concept_id:
                raise Warning("No se ha encontrado el concepto {c} necesario para "
                              "la consulta de cuentas para la causacion de aportes".format(c=apc))
            for acc in ap_concepts[apc]:
                ap_concepts[apc][acc] = getattr(concept_id, '{a}'.format(a=acc))
            ap_concepts[apc]['concept_id'] = concept_id

        aml_data = []

        for kdata in hcfl:
            index = 1
            contract_id = self.env['hr.contract'].browse(kdata[0])
            aa_id = contract_id.analytic_account_id
            employee_id = contract_id.employee_id

            for apc in ap_concepts:
                partner_type = ap_concepts[apc]['partner_type']
                if partner_type == 'eps':
                    c_partner = contract_id.eps
                elif partner_type == 'arl':
                    c_partner = contract_id.arl
                elif partner_type == 'caja':
                    c_partner = contract_id.cajacomp
                elif partner_type == 'cesantias':
                    c_partner = contract_id.cesantias
                elif partner_type == 'pensiones':
                    c_partner = contract_id.pensiones
                elif partner_type == 'other':
                    c_partner = ap_concepts[apc]['concept_id'].partner_other
                else:
                    c_partner = employee_id.partner_id

                apc_amount = kdata[index]
                acc_type = self.get_acc_type(contract_id)
                debit_account = ap_concepts[apc][acc_type+'_debit']
                credit_account = ap_concepts[apc][acc_type+'_credit']
                pyg = [4, 5, 6, 7, 8]
                tot_ded = 0
                if index == 1:  # PENSION
                    ded_pens = po.get_interval_concept('DED_PENS', start_date, liquid_date, contract_id.id)
                    fsol = po.get_interval_concept('FOND_SOL', start_date, liquid_date, contract_id.id)
                    fsub = po.get_interval_concept('FOND_SUB', start_date, liquid_date, contract_id.id)
                    tot_pens = ded_pens + fsol + fsub
                    tot_ded = sum([x[1] for x in tot_pens])
                elif index == 2:  # EPS
                    ded_eps = po.get_interval_concept('DED_EPS', start_date, liquid_date, contract_id.id)
                    tot_ded = sum([x[1] for x in ded_eps])
                    if apc_amount and apc_amount - rp(tot_ded) > 0:
                        global_ibc = orm.fetchall(self._cr, "select global_ibc from hr_contribution_form_line where contract_id = {contract} and contribution_id = {contribution} limit 1".format(
                            contract=contract_id.id, contribution=self.id))
                        if not global_ibc:
                            raise Warning("Como putas el contrato {contract} en esta PILA no tiene ibc global ????? Sea serio calcule primero y luego cause".format(contract=contract_id.name))
                        if not (global_ibc[0][0] >= 10 * smmlv or contract_id.type_id.type_class == 'int' or contract_id.fiscal_type_id.code in ('12', '19')):
                            ded_eps = po.get_interval_concept('DED_EPS', start_date_tmp, liquid_date, contract_id.id)
                            tot_ded_previos = sum([rp(x[1]) for x in ded_eps])
                            ap_previos = """
                            select sum(HCFL.eps_cot) from hr_contribution_form_line as HCFL
                            inner join hr_contribution_form as HCF on HCF.id = HCFL.contribution_id
                            inner join payslip_period as PP on PP.id = HCF.period_id
                            where HCFL.contract_id = {contract}
                            and (HCF.state = 'closed' or HCF.id = {HCF_id})
                            and PP.start_period >= '{sp}' and PP.end_period <= '{ep}'
                            """.format(contract=contract_id.id, HCF_id=self.id,sp=start_date_tmp, ep=liquid_date)
                            ap_previos = sum([rp(x[0]) for x in orm.fetchall(self._cr, ap_previos) if x[0]])
                            if tot_ded_previos == ap_previos:
                                apc_amount, tot_ded = tot_ded_previos, tot_ded_previos
                            else:
                                apc_amount, tot_ded = ap_previos, tot_ded_previos

                amount = apc_amount - tot_ded
                if amount > 0:
                    # DEBIT - GASTOS
                    if not debit_account:
                        raise Warning(u"No se ha definido una cuenta debito para el "
                                      u"concepto {c}".format(c=ap_concepts[apc]['concept_id'].name))
                    aml_data.append({
                        'name': ap_concepts[apc]['concept_id'].name,
                        'ref1': ap_concepts[apc]['concept_id'].code,
                        'date': liquid_date,
                        'ref': employee_id.partner_id.ref,
                        'partner_id': c_partner.id,
                        'account_id': debit_account.id,
                        'journal_id': self.journal_id.id,
                        'period_id': account_period.id,
                        'debit': amount,
                        'credit': 0,
                        'analytic_account_id': aa_id.id if debit_account.code[0] in pyg else False,
                        'tax_code_id': False,
                        'tax_amount': 0,
                        'move_id': self.move_id.id,
                        'state': 'valid',
                        'date_maturity': liquid_date,
                        'contract_id': contract_id.id
                        })

                    # CREDIT CxC 23
                    if not credit_account:
                        raise Warning(u"No se ha definido una cuenta credito para el "
                                      u"concepto {c}".format(c=ap_concepts[apc]['concept_id'].name))
                    aml_data.append({
                        'name': ap_concepts[apc]['concept_id'].name,
                        'ref1': ap_concepts[apc]['concept_id'].code,
                        'date': liquid_date,
                        'ref': employee_id.partner_id.ref,
                        'partner_id': c_partner.id,
                        'account_id': credit_account.id,
                        'journal_id': self.journal_id.id,
                        'period_id': account_period.id,
                        'debit': 0,
                        'credit': amount,
                        'analytic_account_id': aa_id.id if credit_account.code[0] in pyg else False,
                        'tax_code_id': False,
                        'tax_amount': 0,
                        'move_id': self.move_id.id,
                        'state': 'valid',
                        'date_maturity': liquid_date,
                        'contract_id': contract_id.id
                    })
                index += 1
        orm.direct_create(self._cr, self._uid, 'account_move_line', aml_data, company=True, progress=True)
        self.state = 'closed'
        self.create_distribition_analytic(self.move_id.id)
        return

    def create_distribition_analytic(self, move_id):
        move_line_ids = self.env['account.move.line'].search([('move_id','=',move_id)])
        is_hr_roster = orm.fetchall(self._cr,"select id from ir_module_module where state = 'installed' and name = 'hr_roster'")
        is_analytic_cvs = orm.fetchall(self._cr,"select id from ir_module_module where state = 'installed' and name = 'account_analytic_cvs'")
        distribucion_analitica = self.env['hr.roster.close.distribution'] if is_hr_roster else False
        partner_aaa = orm.fetchall(self._cr, "SELECT column_name FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'account_analytic_line' and column_name = 'partner_aaa'")
        analytic_lines_data = []
        for move_line in move_line_ids:
            if  int(move_line.account_id.code[0]) <= 3 and not self.env.user.company_id.config_analytic_global:
                continue
            if not move_line.contract_id:
                raise Warning("El movimieto < {m} > no tiene un contrato asociado".format(m=move_line.name))
            contrato = move_line.contract_id
            if not contrato.employee_id:
                raise Warning("El contrato < {c} > no tiene un empleado asociado".format(c=move_line.contract_id.name))
            employee_id = contrato.employee_id
            if distribucion_analitica:
                distri_employee = distribucion_analitica.search([('employee_id','=',employee_id.id), ('date', '>=', move_line.period_id.date_start),('date', '<=', move_line.period_id.date_stop)])
            else:
                distri_employee = [] # se deja [] por el for que itera distri_employee
            if not distri_employee:
                if not contrato.analytic_account_id:
                    raise Warning("El contrato < {c} > no tiene una cuenta analitica asociada".format(c=contrato.name))
                self._cr.execute('update account_move_line set analytic_account_id = {AA} where id = {AML}'.format(
                    AA=contrato.analytic_account_id.id, AML=move_line.id))
                analytic_line = {
                    'name': move_line.name,
                    'account_id': contrato.analytic_account_id.id, 
                    'journal_id': move_line.journal_id.analytic_journal_id.id,
                    'user_id': self._uid,
                    'date': move_line.date,
                    'ref': move_line.ref,
                    'amount': (move_line.credit - move_line.debit),
                    'general_account_id': move_line.account_id.id,
                    'move_id': move_line.id,

                    'cc1': contrato.analytic_account_id.cc1 if not is_analytic_cvs else contrato.analytic_account_id.regional_id.name,
                    'cc2': contrato.analytic_account_id.cc2 if not is_analytic_cvs else contrato.analytic_account_id.city_id.name,
                    'cc3': contrato.analytic_account_id.cc3 if not is_analytic_cvs else contrato.analytic_account_id.linea_servicio_id.name,
                    'cc4': contrato.analytic_account_id.cc4 if not is_analytic_cvs else contrato.analytic_account_id.sede,
                    'cc5': contrato.analytic_account_id.cc5 if not is_analytic_cvs else contrato.analytic_account_id.puesto,
                }
                if partner_aaa:
                    analytic_line['partner_aaa'] = contrato.analytic_account_id.partner_id.id
                analytic_lines_data.append(analytic_line)
            for dis_emp in distri_employee:
                analytic_line = {
                    'name': move_line.name,
                    'account_id': dis_emp.analytic_account_id.id,
                    'journal_id': move_line.journal_id.analytic_journal_id.id,
                    'user_id': self._uid,
                    'date': move_line.date,
                    'ref': move_line.ref,
                    'amount': (move_line.credit - move_line.debit)*dis_emp.rate/100,
                    'general_account_id': move_line.account_id.id,
                    'move_id': move_line.id,

                    'cc1': dis_emp.analytic_account_id.cc1 if not is_analytic_cvs else dis_emp.analytic_account_id.regional_id.name,
                    'cc2': dis_emp.analytic_account_id.cc2 if not is_analytic_cvs else dis_emp.analytic_account_id.city_id.name,
                    'cc3': dis_emp.analytic_account_id.cc3 if not is_analytic_cvs else dis_emp.analytic_account_id.linea_servicio_id.name,
                    'cc4': dis_emp.analytic_account_id.cc4 if not is_analytic_cvs else dis_emp.analytic_account_id.sede,
                    'cc5': dis_emp.analytic_account_id.cc5 if not is_analytic_cvs else dis_emp.analytic_account_id.puesto,
                }
                if partner_aaa:
                    analytic_line['partner_aaa'] = dis_emp.analytic_account_id.partner_id.id
                analytic_lines_data.append(analytic_line)
        orm.direct_create(self._cr, self._uid, 'account_analytic_line', analytic_lines_data, company=True)
        return True

    def get_contract_repeated(self):
        if self.contract_ids.ids:
            contracts_ids = tuple( self.contract_ids.ids if len(self.contract_ids.ids) > 1 else [self.contract_ids.ids[0],0])
            contracts_ids = 'and contract_id in ' + str(contracts_ids)
        else:
            contracts_ids = ""
        get_contract_repeated_sel = """
        select name
        from hr_contract
        where id in (
            select contract_id from pila_contract_rel where pila_id in (select id from hr_contribution_form where period_id = {periodo})
            {contracts}
            group by contract_id
            having count(pila_id) > 1) """.format(periodo=self.period_id.id, pila=self.id, contracts=contracts_ids)
        contract_repeated = [str(x[0]) for x in orm.fetchall(self._cr, get_contract_repeated_sel)]
        if contract_repeated:
            raise Warning ('Error, hay contratos que estan en varias autoliquidaciones en el mismo periodo, por favor validar los siguientes nombres de contratos: {ids}'.format(ids=contract_repeated))
