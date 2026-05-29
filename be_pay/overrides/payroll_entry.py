# Copyright (c) 2025, Be Pay
# License: MIT

import frappe
from frappe import _
import json
from dateutil.relativedelta import relativedelta

from frappe.model.document import Document
from frappe.utils import (
    DATE_FORMAT,
    add_days,
    add_to_date,
    cint,
    comma_and,
    date_diff,
    flt,
    get_link_to_form,
    getdate,
)

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
    get_accounting_dimensions,
)
from erpnext.accounts.utils import get_fiscal_year
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.payroll.doctype.payroll_entry.payroll_entry import (
    PayrollEntry,
    get_employee_list,
)
try:
    from erpnext.loan_management.doctype.process_loan_interest_accrual.process_loan_interest_accrual import (
        process_loan_interest_accrual_for_term_loans
    )
except ImportError:
    process_loan_interest_accrual_for_term_loans = None


class CustomPayrollEntry(PayrollEntry):
    """Custom Payroll Entry with extended functionality for Be Pay"""

    # ================================================================
    # CORE METHODS
    # ================================================================

    def before_save(self):
        """Auto-create seniority document if setting is enabled"""
        if frappe.db.get_single_value("Custom Paie Settings", "automatic_seniority"):
            args = {
                'doctype': 'Anciennete',
                'company': self.company,
                'payroll_period': self.payroll_period,
                'posting_date': self.posting_date
            }
            if self.branch:
                args.update({"branch": self.branch})
            if self.employment_type:
                args.update({"employment_type": self.employment_type})

            doc = frappe.get_doc(args)
            if doc:
                doc.insert()
                doc.submit()

    def on_submit(self):
        """
        On Payroll Entry submission:
        1. Call native HRMS behavior
        2. Calculate attendance data per employee and per Salary Component
        3. Create/update Pay Attendance List for the period
        """
        super().on_submit()
        self._be_pay_calculate_attendance_for_period()

    # ================================================================
    # SALARY SLIP CREATION
    # ================================================================

    @frappe.whitelist()
    def create_salary_slips(self):
        """
        Creates salary slip for selected employees if not already created
        """
        self.check_permission("write")
        employees = [emp.employee for emp in self.employees]
        
        if employees:
            args = frappe._dict({
                "salary_slip_based_on_timesheet": self.salary_slip_based_on_timesheet,
                "payroll_frequency": self.payroll_frequency,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "company": self.company,
                "posting_date": self.posting_date,
                "deduct_tax_for_unclaimed_employee_benefits": self.deduct_tax_for_unclaimed_employee_benefits,
                "deduct_tax_for_unsubmitted_tax_exemption_proof": self.deduct_tax_for_unsubmitted_tax_exemption_proof,
                "payroll_entry": self.name,
                "exchange_rate": self.exchange_rate,
                "currency": self.currency,
                "eventual": self.eventual,
                "pay_period": self.payroll_period
            })

            full_enqueue = frappe.db.get_single_value('Custom Paie Settings', 'full_enqueue')
            
            if not full_enqueue:
                if len(employees) > 30 or frappe.flags.enqueue_payroll_entry:
                    self.db_set("status", "Queued")
                    frappe.enqueue(
                        self.create_salary_slips_for_employees,
                        timeout=3600,
                        employees=employees,
                        args=args,
                        publish_progress=True,
                    )
                    frappe.msgprint(
                        _("Salary Slip creation is queued. It may take a few minutes"),
                        alert=True,
                        indicator="blue",
                    )
                else:
                    self.create_salary_slips_for_employees(employees, args, publish_progress=False)
                    self.reload()
            else:
                if len(employees) > 0 or frappe.flags.enqueue_payroll_entry:
                    self.db_set("status", "Queued")
                    frappe.enqueue(
                        self.create_salary_slips_for_employees,
                        timeout=3600,
                        employees=employees,
                        args=args,
                        publish_progress=True,
                    )
                    frappe.msgprint(
                        _("Salary Slip creation is queued. It may take a few minutes"),
                        alert=True,
                        indicator="blue",
                    )

    def create_salary_slips_for_employees(self, employees, args, publish_progress=True):
        """Create salary slips for given employees"""
        try:
            if process_loan_interest_accrual_for_term_loans:
                process_loan_interest_accrual_for_term_loans()
            
            # Process partially disbursed loans
            liste = frappe.db.get_list("Loan", "name", {"status": "Partially Disbursed"})
            for i in liste:
                doc = frappe.get_doc({
                    'doctype': 'Loan Disbursement',
                    'disbursement_date': self.end_date,
                    'disbursed_amount': 0,
                    'against_loan': i.name,
                })
                doc.submit()

            payroll_entry = frappe.get_doc("Payroll Entry", args.payroll_entry)
            salary_slips_exist_for = self.get_existing_salary_slips(employees, args)
            jour_ouvrable = frappe.db.get_single_value("Custom Paie Settings", "jour_ouvrable")
            multiple_salary_in_period = frappe.db.get_single_value("Custom Paie Settings", "multiple_salary_in_period")
            count = 0

            for emp in employees:
                employee = frappe.get_doc('Employee', emp)
                if employee.vacation == 1:
                    continue

                leaves = self.calcul_conge_annuel(emp, self.start_date, self.end_date)
                employee.jour_conge = leaves
                employee.save()

                salary_types = frappe.db.get_list(
                    doctype="Salary Structure Assignment",
                    fields=["salary_type", "salary_structure"],
                    filters={"eventual": 0, "employee": emp, "docstatus": 1}
                )

                # Bonus de fin d'année
                bonus_in_separate_slip = frappe.db.get_single_value('Custom Paie Settings', 'bonus_in_separate_slip')
                if bonus_in_separate_slip == 1:
                    if getdate(self.end_date).month == 12:
                        leaves_struc = frappe.db.get_list(
                            doctype="Salary Structure Assignment",
                            fields=["salary_type", "salary_structure"],
                            filters={"eventual": 1, "employee": emp, "docstatus": 1, 'event_name': 'Prime annuelle'}
                        )
                        if len(leaves_struc) > 0:
                            salary_types = salary_types + leaves_struc

                if leaves > 0:
                    leaves_struc = frappe.db.get_list(
                        doctype="Salary Structure Assignment",
                        fields=["salary_type", "salary_structure"],
                        filters={"eventual": 1, "employee": emp, "docstatus": 1, 'event_name': 'Congé Annuel'}
                    )
                    if len(leaves_struc) > 0:
                        salary_types = salary_types + leaves_struc

                if employee.retirement == 1:
                    ret_struc = frappe.db.get_list(
                        doctype="Salary Structure Assignment",
                        fields=["salary_type", "salary_structure"],
                        filters={"eventual": 1, "employee": emp, "docstatus": 1, 'event_name': 'Retraite'}
                    )
                    if len(ret_struc) > 0:
                        salary_types = salary_types + ret_struc

                for t in salary_types:
                    attendances = frappe.db.sql(
                        """
                        SELECT l.*
                        FROM `tabAttendance list` a 
                        INNER JOIN `tabAttendance Line` l ON a.name = l.parent
                        WHERE a.pay_period = '%s' AND employee = '%s' AND a.docstatus = 1
                        """ % (payroll_entry.payroll_period, emp),
                        as_dict=1
                    )

                    if multiple_salary_in_period == 1:
                        exist = frappe.db.exists(
                            "Salary Slip",
                            {
                                "employee": emp,
                                "salary_type": t.salary_type,
                                "pay_period": self.payroll_period,
                                "start_date": ["<=", self.start_date],
                                "end_date": [">=", self.start_date]
                            }
                        )
                    else:
                        exist = frappe.db.exists(
                            "Salary Slip",
                            {
                                "employee": emp,
                                "salary_type": t.salary_type,
                                "pay_period": self.payroll_period
                            }
                        )

                    if not exist:
                        args.update({
                            "doctype": "Salary Slip",
                            "employee": emp,
                            "salary_type": t.salary_type,
                            "salary_structure": t.salary_structure,
                            "employee_category_details": employee.employee_category_details,
                            "anciennete": employee.anciennete,
                            "present_days": (jour_ouvrable - attendances[0].absence) if len(attendances) > 0 else jour_ouvrable,
                            "hours_30": attendances[0].hours_30 if len(attendances) > 0 else 0,
                            "night_hours": attendances[0].night_hours if len(attendances) > 0 else 0,
                            "sunday_hours": attendances[0].sunday_hours if len(attendances) > 0 else 0,
                            "hours_60": attendances[0].hours_60 if len(attendances) > 0 else 0,
                            "absence": attendances[0].absence if len(attendances) > 0 else 0,
                            "child": employee.child,
                            "dependent": employee.dependent
                        })
                        frappe.get_doc(args).insert()
                        count += 1
                        
                        if publish_progress:
                            frappe.publish_progress(
                                count * 100 / len(set(employees) - set(salary_slips_exist_for)),
                                title=_("Creating Salary Slips..."),
                            )

            payroll_entry.db_set({"status": "Submitted", "salary_slips_created": 1, "error_message": ""})

            if salary_slips_exist_for:
                frappe.msgprint(
                    _("Salary Slips already exist for employees {}, and will not be processed by this payroll.").format(
                        frappe.bold(", ".join(emp for emp in salary_slips_exist_for))
                    ),
                    title=_("Message"),
                    indicator="orange",
                )

        except Exception as e:
            frappe.db.rollback()
            self.log_payroll_failure("creation", payroll_entry, e)
        finally:
            frappe.db.commit()
            frappe.publish_realtime("completed_salary_slip_creation")

    # ================================================================
    # HELPER METHODS FOR SALARY SLIPS
    # ================================================================

    def get_existing_salary_slips(self, employees, args):
        """Get existing salary slips for employees"""
        return frappe.db.sql_list(
            """
            select distinct employee, salary_type 
            from `tabSalary Slip`
            where docstatus != 2 and company = %s
                and start_date >= %s and end_date <= %s
                and employee in (%s)
            """ % ("%s", "%s", "%s", ", ".join(["%s"] * len(employees))),
            [args.company, args.start_date, args.end_date] + employees,
        )

    def calcul_absence(self, emp):
        """Calculate absence days for an employee"""
        holiday = get_holiday_dates_for_employee(emp, self.start_date, self.end_date)
        attendance = frappe.db.count(
            'Attendance',
            filters=[
                ['employee', '=', emp],
                ['attendance_date', 'between', [self.start_date, self.end_date]],
                ['status', 'IN', ['Absent', 'On Leave']]
            ]
        )
        return attendance - len(holiday)

    def calcul_conge_annuel(self, emp, from_date, to_date):
        """Calculate annual leave days for an employee"""
        conge = frappe.db.sql_list(
            """
            SELECT a.total_leave_days
            FROM `tabLeave Application` a 
            INNER JOIN `tabLeave Type` t ON a.leave_type = t.name
            WHERE a.employee = %s 
                AND a.from_date BETWEEN %s AND %s 
                AND a.status = 'Approved' 
                AND is_circumstance = 0
            LIMIT 1
            """,
            (emp, from_date, to_date),
        )
        return conge[0] if len(conge) > 0 else 0

    # ================================================================
    # ACCRUAL JOURNAL ENTRY
    # ================================================================

    def make_accrual_jv_entry(self):
        """Create accrual journal entry for payroll"""
        self.check_permission("write")
        earnings = self.get_salary_component_total(component_type="earnings") or {}
        deductions = self.get_salary_component_total(component_type="deductions") or {}
        payroll_payable_account = self.payroll_payable_account
        jv_name = ""
        precision = frappe.get_precision("Journal Entry Account", "debit_in_account_currency")

        if earnings or deductions:
            journal_entry = frappe.new_doc("Journal Entry")
            journal_entry.voucher_type = "Journal Entry"
            journal_entry.user_remark = _("Accrual Journal Entry for salaries from {0} to {1}").format(
                self.start_date, self.end_date
            )
            journal_entry.company = self.company
            journal_entry.posting_date = self.posting_date
            accounting_dimensions = get_accounting_dimensions() or []

            accounts = []
            currencies = []
            payable_amount = 0
            payable_amt2 = 0
            multi_currency = 0
            company_currency = erpnext.get_company_currency(self.company)

            # Earnings
            for acc_cc, amount in earnings.items():
                exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
                    acc_cc[0], amount, company_currency, currencies
                )
                payable_amount += flt(amount, precision)
                payable_amt2 += flt(amt, precision)
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": acc_cc[0],
                            "debit_in_account_currency": flt(amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": acc_cc[1] or self.cost_center,
                            "project": self.project,
                        },
                        accounting_dimensions,
                    )
                )

            # Deductions
            for acc_cc, amount in deductions.items():
                exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
                    acc_cc[0], amount, company_currency, currencies
                )
                payable_amount -= flt(amount, precision)
                payable_amt2 -= flt(amt, precision)
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": acc_cc[0],
                            "credit_in_account_currency": flt(amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": acc_cc[1] or self.cost_center,
                            "project": self.project,
                        },
                        accounting_dimensions,
                    )
                )

            # Payable amount
            exchange_rate, payable_amt = self.get_amount_and_exchange_rate_for_journal_entry(
                payroll_payable_account, payable_amount, company_currency, currencies
            )
            accounts.append(
                self.update_accounting_dimensions(
                    {
                        "account": payroll_payable_account,
                        "credit_in_account_currency": flt(payable_amt, precision),
                        "exchange_rate": flt(exchange_rate),
                        "cost_center": self.cost_center,
                    },
                    accounting_dimensions,
                )
            )
            
            # Round off adjustment
            if flt(payable_amt2 - payable_amt, precision) != 0:
                round_off_account = frappe.get_value("Company", self.company, "round_off_account")
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": round_off_account,
                            "credit_in_account_currency": flt(payable_amt2 - payable_amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": self.cost_center,
                        },
                        accounting_dimensions,
                    )
                )

            journal_entry.set("accounts", accounts)
            if len(currencies) > 1:
                multi_currency = 1
            journal_entry.multi_currency = multi_currency
            journal_entry.title = payroll_payable_account
            journal_entry.save()

            try:
                journal_entry.submit()
                jv_name = journal_entry.name
                self.update_salary_slip_status(jv_name=jv_name)
            except Exception as e:
                if type(e) in (str, list, tuple):
                    frappe.msgprint(e)
                raise

        return jv_name

    # ================================================================
    # EMPLOYEE LIST METHODS
    # ================================================================

    @frappe.whitelist()
    def fill_employee_details(self):
        """Fill employee details based on filters"""
        filters = self.make_filters()
        employees = get_employee_list(
            filters=filters, as_dict=True, ignore_match_conditions=True
        )

        if self.employment_type and employees:
            emp_names = [emp.employee for emp in employees]
            emp_types = frappe.db.get_all(
                "Employee",
                filters={"name": ["in", emp_names]},
                fields=["name", "employment_type"],
            )
            emp_type_map = {e.name: e.employment_type for e in emp_types}
            employees = [
                emp
                for emp in employees
                if emp_type_map.get(emp.employee) == self.employment_type
            ]

        self.set("employees", [])

        if not employees:
            error_msg = _(
                "No employees found for the mentioned criteria:<br>Company: {0}<br>Currency: {1}<br>Payroll Payable Account: {2}"
            ).format(
                frappe.bold(self.company),
                frappe.bold(self.currency),
                frappe.bold(self.payroll_payable_account),
            )
            if self.branch:
                error_msg += "<br>" + _("Branch: {0}").format(frappe.bold(self.branch))
            if self.department:
                error_msg += "<br>" + _("Department: {0}").format(frappe.bold(self.department))
            if self.designation:
                error_msg += "<br>" + _("Designation: {0}").format(frappe.bold(self.designation))
            if self.employment_type:
                error_msg += "<br>" + _("Employment Type: {0}").format(frappe.bold(self.employment_type))
            if self.start_date:
                error_msg += "<br>" + _("Start date: {0}").format(frappe.bold(self.start_date))
            if self.end_date:
                error_msg += "<br>" + _("End date: {0}").format(frappe.bold(self.end_date))
            frappe.throw(error_msg, title=_("No employees found"))

        self.set("employees", employees)
        self.number_of_employees = len(self.employees)
        self.update_employees_with_withheld_salaries()

        return self.get_employees_with_unmarked_attendance()

    def make_filters(self):
        """Create filters for employee selection"""
        filters = super().make_filters()
        filters["employment_type"] = self.get("employment_type")
        return filters

    def get_emp_list(self):
        """
        Returns list of active employees based on selected criteria
        and for which salary structure exists
        """
        self.check_mandatory()
        filters = self.make_filters()
        cond = self.get_filter_condition2(filters)
        cond += self.get_joining_relieving_condition2(self.start_date, self.end_date)

        condition = ""
        if self.payroll_frequency:
            condition = """and payroll_frequency = '%(payroll_frequency)s'""" % {
                "payroll_frequency": self.payroll_frequency
            }

        sal_struct = self.get_sal_struct2(
            self.company, self.currency, self.salary_slip_based_on_timesheet, condition
        )
        
        if sal_struct:
            cond += "and t2.salary_structure IN %(sal_struct)s "
            cond += "and t2.payroll_payable_account = %(payroll_payable_account)s "
            cond += "and %(from_date)s >= t2.from_date"
            emp_list = self.get_emp_list2(sal_struct, cond, self.end_date, self.payroll_payable_account)
            emp_list = self.remove_payrolled_employees2(emp_list, self.start_date, self.end_date)
            return emp_list

    def get_filter_condition2(self, filters):
        """Get filter condition string"""
        cond = ""
        for f in ["company", "branch", "department", "designation", "employment_type"]:
            if filters.get(f):
                cond += " and t1." + f + " = " + frappe.db.escape(filters.get(f))
        return cond

    def get_joining_relieving_condition2(self, start_date, end_date):
        """Get joining/relieving condition string"""
        cond = """
            and ifnull(t1.date_of_joining, '1900-01-01') <= '%(end_date)s'
            and ifnull(t1.relieving_date, '2199-12-31') >= '%(start_date)s'
        """ % {
            "start_date": start_date,
            "end_date": end_date,
        }
        return cond

    def get_sal_struct2(self, company, currency, salary_slip_based_on_timesheet, condition):
        """Get salary structures"""
        return frappe.db.sql_list(
            """
            select name from `tabSalary Structure`
            where docstatus = 1
                and is_active = 'Yes'
                and company = %(company)s
                and currency = %(currency)s
                and ifnull(salary_slip_based_on_timesheet,0) = %(salary_slip_based_on_timesheet)s
                {condition}
            """.format(condition=condition),
            {
                "company": company,
                "currency": currency,
                "salary_slip_based_on_timesheet": salary_slip_based_on_timesheet,
            },
        )

    def get_emp_list2(self, sal_struct, cond, end_date, payroll_payable_account):
        """Get employee list based on criteria"""
        return frappe.db.sql(
            """
            select distinct t1.name as employee, t1.employee_name, t1.department, t1.designation
            from `tabEmployee` t1, `tabSalary Structure Assignment` t2
            where t1.name = t2.employee
                and t2.docstatus = 1
                and t1.status != 'Inactive'
                and t1.vacation = 0
                %s 
            order by t2.from_date desc
            """ % cond,
            {
                "sal_struct": tuple(sal_struct),
                "from_date": end_date,
                "payroll_payable_account": payroll_payable_account,
            },
            as_dict=True,
        )

    def remove_payrolled_employees2(self, emp_list, start_date, end_date):
        """Remove already payrolled employees"""
        new_emp_list = []
        for employee_details in emp_list:
            if not frappe.db.exists(
                "Salary Slip",
                {
                    "employee": employee_details.employee,
                    "start_date": start_date,
                    "end_date": end_date,
                    "docstatus": 1,
                },
            ):
                new_emp_list.append(employee_details)
        return new_emp_list

    # ================================================================
    # ATTENDANCE CALCULATION
    # ================================================================

    def _be_pay_calculate_attendance_for_period(self):
        """
        Aggregates Attendance for each employee over the Payroll Entry period,
        calculates hours by Salary Component (via Shift Type.custom_salary_component)
        and populates a Pay Attendance List document.
        """
        if not self.start_date or not self.end_date or not self.employees:
            return

        logger = frappe.logger("be_pay_payroll")

        # Get configured Salary Components from Pay Payroll Settings
        settings = frappe.get_single("Pay Payroll Settings")
        configured_components = [
            row.salary_component
            for row in (settings.attendance_salary_components or [])
            if row.salary_component
        ]

        if not configured_components:
            logger.info(
                "No Salary Component configured in Pay Payroll Settings => "
                "no aggregation by component."
            )

        # Identify or create Pay Attendance List for the period
        pay_period_label = self.payroll_period or f"{self.start_date}_to_{self.end_date}"

        existing_list = frappe.get_all(
            "Pay Attendance List",
            filters={"pay_period": pay_period_label},
            fields=["name", "docstatus"],
            limit=1,
        )

        if existing_list:
            att_list = frappe.get_doc("Pay Attendance List", existing_list[0].name)
            if att_list.docstatus == 1:
                att_list.cancel()
                att_list = frappe.new_doc("Pay Attendance List")
                att_list.start_date = self.start_date
                att_list.end_date = self.end_date
                att_list.pay_period = pay_period_label
            elif att_list.docstatus == 2:
                att_list = frappe.new_doc("Pay Attendance List")
                att_list.start_date = self.start_date
                att_list.end_date = self.end_date
                att_list.pay_period = pay_period_label
            else:
                att_list.set("attendance_line", [])
        else:
            att_list = frappe.new_doc("Pay Attendance List")
            att_list.start_date = self.start_date
            att_list.end_date = self.end_date
            att_list.pay_period = pay_period_label

        # Aggregate attendance per employee
        for emp_row in self.employees:
            employee = emp_row.employee
            employee_name = emp_row.employee_name or frappe.db.get_value(
                "Employee", employee, "employee_name"
            )

            attendances = frappe.get_all(
                "Attendance",
                filters={
                    "employee": employee,
                    "attendance_date": ["between", [self.start_date, self.end_date]],
                    "docstatus": 1,
                },
                fields=["name", "shift", "custom_working_hours", "working_hours", "attendance_date", "status"],
            )

            if not attendances:
                continue

            # Aggregation by salary_component
            agg = {}
            for att in attendances:
                shift_name = att.shift
                if not shift_name:
                    continue

                salary_component = frappe.db.get_value(
                    "Shift Type", shift_name, "custom_salary_component"
                )
                if not salary_component:
                    continue

                if salary_component not in configured_components:
                    continue

                working_hours = att.custom_working_hours or 0.0
                agg[salary_component] = agg.get(salary_component, 0.0) + working_hours

            for salary_component, total_hours in agg.items():
                att_list.append(
                    "attendance_line",
                    {
                        "employee": employee,
                        "employee_name": employee_name,
                        "salary_component": salary_component,
                        "hours": round(total_hours, 2),
                    },
                )

        # Overtime calculation
        from be_pay.utils.overtime_utils import (
            get_active_overtime_rules,
            distribute_overtime_for_attendance,
        )

        ot_rules = get_active_overtime_rules(self.company)

        for emp_row in self.employees:
            employee = emp_row.employee
            employee_name = emp_row.employee_name or frappe.db.get_value(
                "Employee", employee, "employee_name"
            )

            attendances = frappe.get_all(
                "Attendance",
                filters={
                    "employee": employee,
                    "attendance_date": ["between", [self.start_date, self.end_date]],
                    "docstatus": 1,
                },
                fields=["name", "shift", "custom_working_hours", "working_hours", "attendance_date", "status"],
            )

            if not attendances:
                continue

            overtime_agg = {}
            for att in attendances:
                att.working_hours = att.get("custom_working_hours") or att.get("working_hours") or 0
                dist = distribute_overtime_for_attendance(att, ot_rules)
                for fieldname, hours in dist.items():
                    overtime_agg[fieldname] = overtime_agg.get(fieldname, 0) + hours

            if overtime_agg:
                hs_component = self._get_hs_salary_component()
                line_data = {
                    "employee": employee,
                    "employee_name": employee_name,
                    "salary_component": hs_component,
                    "hours": 0,
                    "is_overtime_line": 1,
                }
                line_data.update(overtime_agg)
                att_list.append("attendance_line", line_data)

        # Save and submit Pay Attendance List
        if att_list.attendance_line:
            att_list.save(ignore_permissions=True)
            att_list.submit()
            logger.info(
                "Pay Attendance List %s created/updated (%s lines).",
                att_list.name,
                len(att_list.attendance_line),
            )
        else:
            logger.info(
                "No attendance lines to generate for period %s.",
                pay_period_label,
            )

    def _get_hs_salary_component(self):
        """
        Returns a valid Salary Component to use for overtime lines
        (avoids Frappe deletion of a child line with empty Link field).
        """
        candidates = ["Heure Supplémentaire", "Basic"]
        for c in candidates:
            if frappe.db.exists("Salary Component", c):
                return c
        first = frappe.get_all("Salary Component", fields=["name"], limit=1)
        return first[0].name if first else None

    # ================================================================
    # ERROR HANDLING
    # ================================================================

    def log_payroll_failure(self, process, payroll_entry, error):
        """Log payroll processing failure"""
        error_log = frappe.log_error(
            title=_("Salary Slip {0} failed for Payroll Entry {1}").format(process, payroll_entry.name)
        )
        message_log = frappe.message_log.pop() if frappe.message_log else str(error)

        try:
            error_message = json.loads(message_log).get("message")
        except Exception:
            error_message = message_log

        error_message += "\n" + _("Check Error Log {0} for more details.").format(
            get_link_to_form("Error Log", error_log.name)
        )

        payroll_entry.db_set({"error_message": error_message, "status": "Failed"})