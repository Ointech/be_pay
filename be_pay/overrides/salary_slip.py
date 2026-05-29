# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Salary Slip pour Be Pay.

Intègre les heures de présence, les congés, les avances sur salaire,
les calculs d'ancienneté, les prêts et les heures supplémentaires.
"""

import frappe
from frappe import _, msgprint
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	flt,
	formatdate,
	get_first_day,
	getdate,
	money_in_words,
	rounded,
)
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from hrms.payroll.doctype.salary_slip.salary_slip_loan_utils import get_payroll_payable_account
from hrms.payroll.doctype.payroll_period.payroll_period import (
	get_payroll_period,
	get_period_factor,
)
from collections import defaultdict

# Tentative d'import des modules loan (legacy ERPNext)
try:
	from erpnext.loan_management.doctype.process_loan_interest_accrual.process_loan_interest_accrual import (
		process_loan_interest_accrual_for_term_loans,
	)
	from erpnext.loan_management.doctype.loan_repayment.loan_repayment import (
		calculate_amounts,
		create_repayment_entry,
	)

	LOAN_MANAGEMENT_AVAILABLE = True
except ImportError:
	LOAN_MANAGEMENT_AVAILABLE = False
	calculate_amounts = None
	create_repayment_entry = None
	process_loan_interest_accrual_for_term_loans = None


class CustomSalarySlip(SalarySlip):
	"""
	Extension de la classe Salary Slip pour la logique Be Pay.
	"""

	# ------------------------------------------------------------------
	# Propriétés & helpers legacy
	# ------------------------------------------------------------------
	@property
	def remaining_sub_periods(self):
		if not hasattr(self, "_remaining_sub_periods"):
			self._remaining_sub_periods = get_period_factor(
				self.employee,
				self.start_date,
				self.end_date,
				self.payroll_frequency,
				self.payroll_period,
			)[1]
		return self._remaining_sub_periods

	# ------------------------------------------------------------------
	# Hooks cycle de vie (Be Pay)
	# ------------------------------------------------------------------
	def before_insert(self):
		self._be_pay_fetch_attendance_data()

	def before_save(self):
		self._be_pay_fetch_attendance_data()
		self._be_pay_fetch_mise_a_pied()
		self._be_pay_fetch_final_settlement()
		self._be_pay_fetch_leave_provision()
		self._be_pay_fetch_salary_advance()
		self._be_pay_fetch_bank_info()
		self._be_pay_calculate_anciennete()
		self._be_pay_update_leave_taken()
		self._be_pay_populate_overtime_table()

	def before_validate(self):
		self._be_pay_calculate_anciennete()

	def before_submit(self):
		self._be_pay_assign_category_salary()

	def after_insert(self):
		self._be_pay_assign_category_salary()

	def on_submit(self):
		if getdate(self.end_date).month == 12:
			self._be_pay_settle_gratuity_provision()
		super().on_submit()
		self._be_pay_make_loan_repayment_entry()

	def on_cancel(self):
		if getdate(self.end_date).month == 12:
			self._be_pay_restore_gratuity_provision()
		super().on_cancel()
		self._be_pay_cancel_loan_repayment_entry()

	# ------------------------------------------------------------------
	# Override méthodes standard (legacy conservées)
	# ------------------------------------------------------------------
	def check_existing(self):
		if not self.salary_slip_based_on_timesheet:
			cond = ""
			if self.payroll_entry:
				cond += "and payroll_entry = '{0}'".format(self.payroll_entry)
			ret_exist = frappe.db.sql(
				"""select name from `tabSalary Slip`
					where start_date = %s and end_date = %s and docstatus != 2
					and employee = %s and name != %s and salary_type = %s {0}""".format(
					cond
				),
				(self.start_date, self.end_date, self.employee, self.name, self.salary_type),
			)
			if ret_exist:
				frappe.throw(
					_("Salary Slip of employee {0} already created for this period").format(self.employee)
				)
		else:
			for data in self.timesheets:
				if frappe.db.get_value("Timesheet", data.time_sheet, "status") == "Payrolled":
					frappe.throw(
						_(
							"Salary Slip of employee {0} already created for time sheet {1}"
						).format(self.employee, data.time_sheet)
					)

	@frappe.whitelist()
	def get_emp_and_working_day_details(self):
		"""First time, load all the components from salary structure"""
		if self.employee:
			self.set("earnings", [])
			self.set("deductions", [])
			if hasattr(self, "loans"):
				self.set("loans", [])

			if not self.salary_slip_based_on_timesheet:
				self.get_date_details()

			joining_date, relieving_date = frappe.get_cached_value(
				"Employee", self.employee, ("date_of_joining", "relieving_date")
			)

			self.validate_dates()

			# get leave details
			self.get_working_days_details()
			struct = self.salary_structure or self.check_sal_struct()

			if struct:
				self._salary_structure_doc = frappe.get_doc("Salary Structure", struct)
				self.salary_slip_based_on_timesheet = (
					self._salary_structure_doc.salary_slip_based_on_timesheet or 0
				)
				self.set_time_sheet()
				self.pull_sal_struct()
				ps = frappe.db.get_value(
					"Payroll Settings",
					None,
					["payroll_based_on", "consider_unmarked_attendance_as"],
					as_dict=1,
				)
				return [ps.payroll_based_on, ps.consider_unmarked_attendance_as]

	def get_working_days_details(self, lwp=None, for_preview=0, lwp_days_corrected=None):
		"""
		Override qui conserve la logique standard HRMS puis enrichit
		la table `leave_taken` avec les détails LWP / PPL.
		"""
		super().get_working_days_details(lwp, for_preview, lwp_days_corrected)
		if for_preview:
			return

		# Enrichissement legacy : détail des congés LWP/PPL pris
		self._be_pay_calculate_lwp_or_ppl_based_on_leave_application()

	def calculate_net_pay(self, skip_tax_breakup_computation=False):
		"""
		Override pour conditionner le remplissage des prêts à `is_main_salary`
		et prendre en compte la devise étrangère des remboursements.
		"""
		# Appel standard qui calcule gross, deductions, remaining_sub_periods, taxe…
		super().calculate_net_pay(skip_tax_breakup_computation)

		# Si c'est le salaire principal, on reprend la logique legacy de prêt
		if self.is_main_salary and LOAN_MANAGEMENT_AVAILABLE:
			self._be_pay_set_loan_repayment()
			self.set_net_pay()

	def set_totals(self):
		"""Override pour intégrer le remboursement de prêt en devise étrangère."""
		super().set_totals()
		if self.salary_slip_based_on_timesheet != 1:
			total_loan = flt(self.get("total_loan_repayment_foreign_currency")) or flt(
				self.get("total_loan_repayment")
			)
			self.net_pay = flt(self.gross_pay) - flt(self.total_deduction) - total_loan
			self.set_base_totals()

	def set_net_pay(self):
		"""Override pour prendre en compte le remboursement de prêt en devise étrangère."""
		self.total_deduction = self.get_component_totals("deductions")
		self.base_total_deduction = flt(
			flt(self.total_deduction) * flt(self.exchange_rate),
			self.precision("base_total_deduction"),
		)
		total_loan = flt(self.get("total_loan_repayment_foreign_currency")) or flt(
			self.get("total_loan_repayment")
		)
		self.net_pay = flt(self.gross_pay) - (flt(self.total_deduction) + total_loan)
		self.rounded_total = rounded(self.net_pay)
		self.base_net_pay = flt(
			flt(self.net_pay) * flt(self.exchange_rate), self.precision("base_net_pay")
		)
		self.base_rounded_total = flt(rounded(self.base_net_pay), self.precision("base_net_pay"))
		if self.hour_rate:
			self.base_hour_rate = flt(
				flt(self.hour_rate) * flt(self.exchange_rate), self.precision("base_hour_rate")
			)
		self.set_net_total_in_words()

	# ------------------------------------------------------------------
	# Logique de prêt (legacy – defensive si erpnext.loan_management absent)
	# ------------------------------------------------------------------
	def get_loan_details(self):
		if not LOAN_MANAGEMENT_AVAILABLE:
			return []

		loan_details = frappe.get_all(
			"Loan",
			fields=[
				"name",
				"interest_income_account",
				"loan_account",
				"loan_type",
				"is_term_loan",
				"exchange_rate",
			],
			filters={
				"applicant": self.employee,
				"docstatus": 1,
				"company": self.company,
				"repay_from_salary_slip": 1,
			},
		)
		if loan_details:
			for loan in loan_details:
				if loan.is_term_loan and process_loan_interest_accrual_for_term_loans:
					process_loan_interest_accrual_for_term_loans(
						posting_date=self.posting_date,
						loan_type=loan.loan_type,
						loan=loan.name,
					)
		return loan_details

	def _be_pay_set_loan_repayment(self):
		if not LOAN_MANAGEMENT_AVAILABLE:
			return

		self.total_loan_repayment = 0
		self.total_interest_amount = 0
		self.total_principal_amount = 0
		self.total_loan_repayment_foreign_currency = 0
		self.total_interest_amount_foreign_currency = 0
		self.total_principal_amount_foreign_currency = 0

		if not self.get("loans"):
			for loan in self.get_loan_details():
				amt = calculate_amounts(loan.name, self.posting_date, "Regular Payment")
				if amt.get("interest_amount") or amt.get("payable_principal_amount"):
					total_pmt = flt(amt["interest_amount"]) + flt(amt["payable_principal_amount"])
					er = flt(loan.exchange_rate) or 1
					self.append(
						"loans",
						{
							"loan": loan.name,
							"total_payment": total_pmt,
							"interest_amount": amt["interest_amount"],
							"principal_amount": amt["payable_principal_amount"],
							"loan_account": loan.loan_account,
							"interest_income_account": loan.interest_income_account,
							"total_payment_foreign_currency": total_pmt / er,
							"interest_amount_foreign_currency": amt["interest_amount"] / er,
							"principal_amount_foreign_currency": amt["payable_principal_amount"] / er,
							"loan_exchange_rate": er,
							"loan_type": loan.loan_type,
						},
					)

		for payment in self.get("loans"):
			amt = calculate_amounts(payment.loan, self.posting_date, "Regular Payment")
			total_amount = flt(amt["interest_amount"]) + flt(amt["payable_principal_amount"])
			if payment.total_payment > total_amount:
				frappe.throw(
					_(
						"""Row {0}: Paid amount {1} is greater than pending accrued amount {2} against loan {3}"""
					).format(
						payment.idx,
						frappe.bold(payment.total_payment),
						frappe.bold(total_amount),
						frappe.bold(payment.loan),
					)
				)

			self.total_interest_amount += flt(payment.interest_amount)
			self.total_principal_amount += flt(payment.principal_amount)
			self.total_loan_repayment += flt(payment.total_payment)
			self.total_interest_amount_foreign_currency += flt(
				payment.interest_amount_foreign_currency
			)
			self.total_principal_amount_foreign_currency += flt(
				payment.principal_amount_foreign_currency
			)
			self.total_loan_repayment_foreign_currency += flt(
				payment.total_payment_foreign_currency
			)

	def _be_pay_make_loan_repayment_entry(self):
		if not LOAN_MANAGEMENT_AVAILABLE or not self.get("loans"):
			return

		payroll_payable_account = get_payroll_payable_account(self.company, self.payroll_entry)
		for loan in self.loans:
			if not loan.total_payment:
				continue
			try:
				repayment_entry = create_repayment_entry(
					loan.loan,
					self.employee,
					self.company,
					self.posting_date,
					loan.loan_type,
					"Regular Payment",
					loan.interest_amount,
					loan.principal_amount,
					loan.total_payment,
					payroll_payable_account=payroll_payable_account,
				)
				repayment_entry.save()
				repayment_entry.submit()
				frappe.db.set_value(
					"Salary Slip Loan", loan.name, "loan_repayment_entry", repayment_entry.name
				)
			except Exception:
				frappe.log_error(
					title=_("Loan Repayment Entry Failed"),
					message=frappe.get_traceback(),
				)

	def _be_pay_cancel_loan_repayment_entry(self):
		if not LOAN_MANAGEMENT_AVAILABLE or not self.get("loans"):
			return
		for loan in self.loans:
			if loan.loan_repayment_entry:
				try:
					repayment_entry = frappe.get_doc("Loan Repayment", loan.loan_repayment_entry)
					repayment_entry.cancel()
				except Exception:
					frappe.log_error(
						title=_("Loan Repayment Cancellation Failed"),
						message=frappe.get_traceback(),
					)

	# ------------------------------------------------------------------
	# Logique de présence / congé / décompte (Be Pay)
	# ------------------------------------------------------------------
	def _be_pay_fetch_attendance_data(self):
		if not self.pay_period or not self.employee:
			return

		from be_pay.utils.payroll_utils import get_attendance_summary

		summary = get_attendance_summary(self.pay_period, self.employee)
		if not summary:
			return

		self.custom_heure_suplementaire = summary.get("sunday_hours", 0)
		self.custom_absences = summary.get("absence", 0)
		self.custom_jours_mise_a_pied = summary.get("pay_absence", 0)
		self.custom_presence = summary.get("days", 0)
		self.custom_h30 = summary.get("hours_30", 0)
		self.custom_h60 = summary.get("hours_60", 0)
		self.custom_h100 = summary.get("sunday_hours", 0)
		self.custom_abscences = summary.get("absence", 0)
		self.custom_sm = summary.get("hours", 0)

		# Heures de nuit (directement depuis Pay Attendance Line)
		self.night_hours = summary.get("night_hours", 0)

	def _be_pay_fetch_mise_a_pied(self):
		if not self.employee or not self.start_date or not self.end_date:
			return

		results = frappe.db.sql(
			"""
			SELECT
				SUM(
					DATEDIFF(
						LEAST(s.to_date, %(end_date)s),
						GREATEST(s.from_date, %(start_date)s)
					) + 1
				) AS total_days
			FROM `tabLeave Application` s
			WHERE s.employee = %(employee)s
				AND s.docstatus = 1
				AND s.from_date <= %(end_date)s
				AND s.to_date >= %(start_date)s
				AND s.leave_type = %(leave_type)s
			""",
			{
				"employee": self.employee,
				"start_date": self.start_date,
				"end_date": self.end_date,
				"leave_type": "Mise à pied",
			},
			as_dict=True,
		)

		if results and results[0].total_days:
			self.custom_jours_mise_a_pied = results[0].total_days
		else:
			self.custom_jours_mise_a_pied = 0

	def _be_pay_fetch_final_settlement(self):
		if not self.employee or not self.start_date or not self.end_date:
			return

		decompte_list = frappe.db.sql(
			"""
			SELECT *
			FROM `tabFinal Settlement`
			WHERE employee = %s
				AND date_fin_contrat BETWEEN %s AND %s
				AND docstatus = 1
			""",
			(self.employee, self.start_date, self.end_date),
			as_dict=True,
		)

		if decompte_list:
			self.custom_total_days = decompte_list[0].total_jours
			self.custom_jour_preste = decompte_list[0].jour_preste
		else:
			self.custom_total_days = 0
			self.custom_jour_preste = 0

	def _be_pay_fetch_leave_provision(self):
		if not self.employee or not self.end_date:
			return

		projet_val = frappe.utils.getdate(self.end_date).year

		periods = frappe.get_all(
			"Pay Provision",
			filters={"fiscal_year": projet_val, "employment_type": self.employment_type},
			fields=["name", "start_date", "end_date"],
			limit=1,
		)

		if not periods:
			return

		self.from_date = periods[0].start_date
		self.to_date = periods[0].end_date

		conge_list = frappe.db.sql(
			"""
			SELECT *
			FROM `tabProvision Ratio`
			WHERE employee = %s AND parent = %s
			""",
			(self.employee, periods[0].name),
			as_dict=True,
		)

		if conge_list:
			self.leave_allouer = (
				int(conge_list[0].pris or 0)
				+ int(conge_list[0].total or 0)
				- int(conge_list[0].report or 0)
			)
			self.pris = conge_list[0].pris
			self.reste_a_prendre = conge_list[0].total
			self.custom_repport = conge_list[0].report

	def _be_pay_fetch_salary_advance(self):
		if not self.employee or not self.start_date or not self.end_date:
			return

		result = frappe.db.sql(
			"""
			SELECT MAX(incentive_amount) AS amount
			FROM `tabEmployee Incentive`
			WHERE docstatus = 1
				AND salary_component = 'Salary Advance'
				AND employee = %s
				AND payroll_date BETWEEN %s AND %s
			""",
			(self.employee, self.start_date, self.end_date),
		)

		if result and result[0][0]:
			self.custom_total_avance = result[0][0]

	def _be_pay_fetch_bank_info(self):
		if not self.employee:
			return

		emp = frappe.db.get_value("Employee", self.employee, "local_bank", as_dict=True)

		if emp and not self.custom_get_local_bank:
			self.bank = emp.local_bank

		if self.net_pay:
			self.autres = float(self.net_pay)
			if self.cash is not None and self.bank is not None:
				self.autres = float(self.net_pay) - float(self.cash) - float(self.bank)
			elif self.cash is not None:
				self.autres = float(self.net_pay) - float(self.cash)
			elif self.bank is not None and self.bank != 0:
				self.autres = 0
			else:
				self.autres = float(self.net_pay)

	def _be_pay_calculate_anciennete(self):
		if not self.employee:
			return

		employee_doc = frappe.get_doc("Employee", self.employee)

		from be_pay.utils.payroll_utils import calculate_anciennete

		anciennete = calculate_anciennete(employee_doc.date_of_joining)
		self.anciennete = anciennete
		employee_doc.anciennete = anciennete

		if employee_doc.scheduled_confirmation_date:
			anciennete_fin = calculate_anciennete(employee_doc.scheduled_confirmation_date)
			self.custom_anciennete_fin_prestation = anciennete_fin
			employee_doc.custom_ancienneté_fin_préstation = anciennete_fin

		employee_doc.save()

	def _be_pay_update_leave_taken(self):
		"""
		Met à jour la table `leave_taken` (Pay Leave Taken) avec les congés pris.
		Correspond au remplacement legacy de `conge_pris`.
		"""
		if not self.employee or not self.start_date or not self.end_date:
			return

		from be_pay.utils.payroll_utils import get_leave_taken

		leaves = get_leave_taken(self.employee, self.start_date, self.end_date)
		if not leaves:
			return

		# On vide puis reconstruit pour éviter les doublons
		self.set("leave_taken", [])

		for leave in leaves:
			total_days = flt(leave.total_leave_days)
			if total_days > 26:
				total_days = 26

			self.append(
				"leave_taken",
				{
					"leave_type": leave.leave_type,
					"pay_day": total_days,
					"pay_fraction": 0,
				},
			)

	def _be_pay_calculate_lwp_or_ppl_based_on_leave_application(self):
		"""
		Logique legacy de calcul LWP/PPL enrichissant `leave_taken`.
		Appelée après le calcul standard des jours de travail.
		"""
		if not self.employee or not self.start_date or not self.end_date:
			return

		payroll_settings = frappe.get_cached_doc("Payroll Settings")

		if not payroll_settings or payroll_settings.payroll_based_on != "Leave":
			return

		raw_holidays = self.get_holidays_for_employee(self.start_date, self.end_date) or []
		holidays = [str(h) for h in raw_holidays]
		working_days = date_diff(self.end_date, self.start_date) + 1
		working_days_list = [
			add_days(getdate(self.start_date), days=day) for day in range(0, working_days)
		]

		daily_wages_fraction_for_half_day = (
			flt(payroll_settings.daily_wages_fraction_for_half_day) or 0.5
		)

		leave_type_lwp = []
		holidays_str = "','".join(holidays)

		for d in range(len(working_days_list)):
			date = add_days(cstr(getdate(self.start_date)), d)
			leave = get_lwp_or_ppl_for_date_2(date, self.employee, holidays_str)

			if leave:
				is_half_day_leave = cint(leave[0].is_half_day)
				is_partially_paid_leave = cint(leave[0].is_ppl)
				fraction_of_daily_salary_per_leave = flt(leave[0].fraction_of_daily_salary_per_leave)

				equivalent_lwp_count = (
					(1 - daily_wages_fraction_for_half_day) if is_half_day_leave else 1
				)

				if is_partially_paid_leave:
					equivalent_lwp_count *= (
						fraction_of_daily_salary_per_leave
						if fraction_of_daily_salary_per_leave
						else 1
					)

				leave_type_lwp.append(
					{
						"leave_type": leave[0].name,
						"pay_day": equivalent_lwp_count,
						"pay_fraction": fraction_of_daily_salary_per_leave,
					}
				)

		# Agrégation par leave_type
		occurrence_counts = defaultdict(lambda: {"pay_day": 0, "pay_fraction": 0})
		for entry in leave_type_lwp:
			lt = entry["leave_type"]
			occurrence_counts[lt]["pay_day"] += entry["pay_day"]
			if entry["pay_fraction"]:
				occurrence_counts[lt]["pay_fraction"] = entry["pay_fraction"]

		# On fusionne avec les lignes existantes de leave_taken (même type = on écrase les jours LWP)
		existing = {row.leave_type: row for row in self.get("leave_taken", [])}
		for lt, data in occurrence_counts.items():
			if lt in existing:
				existing[lt].pay_day = data["pay_day"]
				existing[lt].pay_fraction = data["pay_fraction"]
			else:
				self.append(
					"leave_taken",
					{
						"leave_type": lt,
						"pay_day": data["pay_day"],
						"pay_fraction": data["pay_fraction"],
					},
				)

		self.total_leaves = sum(data["pay_day"] for data in occurrence_counts.values())

	def _be_pay_assign_category_salary(self):
		if not self.employee:
			return

		employee_doc = frappe.get_doc("Employee", self.employee)

		salary = employee_doc.pay_basic_salary_per_day or 0
		self.custom_salaire_categorise_au_depart = salary
		self.basic_salary_per_day = salary

	def _be_pay_calculate_anciennete_day(self):
		if not self.date_embauche or not self.to_date:
			return

		from be_pay.utils.payroll_utils import calculate_months_between

		months = calculate_months_between(self.date_embauche, self.to_date)
		self.anciennete_day = months / 12

	def _be_pay_populate_overtime_table(self):
		"""
		Peuple le tableau custom 'custom_hs_details' sur le Salary Slip
		avec les données de Pay Attendance Line (ou directement Attendance).
		"""
		if not self.company or not self.employee:
			return

		self.set("custom_hs_details", [])

		try:
			from be_pay.utils.overtime_utils import (
				get_active_overtime_rules,
				get_overtime_settings,
				distribute_overtime_for_attendance,
			)
		except Exception:
			return

		settings = get_overtime_settings(self.company)
		rules = get_active_overtime_rules(self.company) if settings else []

		# Taux horaire pour calcul des montants
		hourly_rate = 0
		if settings:
			try:
				ot_doc = frappe.get_doc("Be Pay Overtime Settings", settings.name)
				base_components = [c.salary_component for c in ot_doc.base_salary_components]
				base_amount = sum(
					flt(r.amount) for r in self.earnings if r.salary_component in base_components
				)
				if base_amount and self.total_working_days and settings.standard_daily_hours:
					hourly_rate = flt(base_amount) / flt(self.total_working_days) / flt(
						settings.standard_daily_hours
					)
			except Exception:
				pass

		# --- Source 1 : Pay Attendance List ---
		lines = []
		pay_period_label = getattr(self, "pay_period", None) or (
			f"{self.start_date}_to_{self.end_date}"
			if self.start_date and self.end_date
			else None
		)

		if pay_period_label:
			pal_list = frappe.get_all(
				"Pay Attendance List",
				filters={"pay_period": pay_period_label, "docstatus": 1},
				fields=["name"],
				limit=1,
			)
			if pal_list:
				lines = frappe.get_all(
					"Pay Attendance Line",
					filters={"parent": pal_list[0].name, "employee": self.employee},
					fields=["*"],
				)

		# --- Source 2 : Attendance directe (fallback) ---
		if not lines and self.start_date and self.end_date:
			attendances = frappe.get_all(
				"Attendance",
				filters={
					"employee": self.employee,
					"attendance_date": ["between", [self.start_date, self.end_date]],
					"docstatus": 1,
				},
				fields=[
					"name",
					"shift",
					"custom_working_hours",
					"working_hours",
					"attendance_date",
					"status",
				],
			)
			if attendances:
				for att in attendances:
					att.working_hours = (
						att.get("custom_working_hours") or att.get("working_hours") or 0
					)
					dist = distribute_overtime_for_attendance(att, rules)
					if dist:
						for fieldname, hours in dist.items():
							label = next(
								(
									r.target_label
									for r in rules
									if r.target_fieldname == fieldname
								),
								fieldname,
							)
							mult = next(
								(
									flt(r.multiplier) / 100.0
									if flt(r.multiplier) > 1
									else flt(r.multiplier)
									for r in rules
									if r.target_fieldname == fieldname
								),
								1,
							)
							amount = flt(hourly_rate * hours * mult, 2)
							self.append(
								"custom_hs_details",
								{
									"label": f"{label} ({att.attendance_date})",
									"hours": hours,
									"days": 0,
									"amount": amount,
								},
							)
				return

		if not lines:
			return

		# Remplir le tableau depuis Pay Attendance Line
		for line in lines:
			if (
				line.get("salary_component")
				and flt(line.get("hours")) > 0
				and not line.get("is_overtime_line")
			):
				self.append(
					"custom_hs_details",
					{
						"label": line.salary_component,
						"hours": flt(line.hours, 2),
						"days": line.get("days") or 0,
						"amount": 0,
					},
				)

			for rule in rules:
				val = flt(line.get(rule.target_fieldname))
				if val > 0:
					mult = (
						flt(rule.multiplier) / 100.0
						if flt(rule.multiplier) > 1
						else flt(rule.multiplier)
					)
					amount = flt(hourly_rate * val * mult, 2)
					self.append(
						"custom_hs_details",
						{
							"label": rule.target_label,
							"hours": val,
							"days": 0,
							"amount": amount,
						},
					)

	def _be_pay_settle_gratuity_provision(self):
		"""Solde la provision gratification (pris = total, total = 0)."""
		frappe.db.sql(
			"""
			UPDATE `tabPay Provision Gratuity` r
			INNER JOIN `tabPay Provision` p ON p.name = r.parent
			SET r.pay_taken = r.pay_total,
				r.pay_total = 0
			WHERE r.employee = %(employee)s
			  AND %(to_date)s BETWEEN p.start_date AND p.end_date
			""",
			{"employee": self.employee, "to_date": self.end_date},
		)

	def _be_pay_restore_gratuity_provision(self):
		"""Restaure la provision gratification après annulation."""
		frappe.db.sql(
			"""
			UPDATE `tabPay Provision Gratuity` r
			INNER JOIN `tabPay Provision` p ON p.name = r.parent
			SET r.pay_taken = 0,
				r.pay_total = r.pay_report
					+ r.pay_january + r.pay_february + r.pay_march
					+ r.pay_april + r.pay_may + r.pay_june
					+ r.pay_july + r.pay_august + r.pay_september
					+ r.pay_october + r.pay_november + r.pay_december
			WHERE r.employee = %(employee)s
			  AND %(to_date)s BETWEEN p.start_date AND p.end_date
			""",
			{"employee": self.employee, "to_date": self.end_date},
		)


# ------------------------------------------------------------------------------
# Fonctions standalone
# ------------------------------------------------------------------------------

def get_lwp_or_ppl_for_date_2(date, employee, holidays):
	LeaveApplication = frappe.qb.DocType("Leave Application")
	LeaveType = frappe.qb.DocType("Leave Type")

	is_half_day = (
		frappe.qb.terms.Case()
		.when(
			(
				(LeaveApplication.half_day_date == date)
				| (LeaveApplication.from_date == LeaveApplication.to_date)
			),
			LeaveApplication.half_day,
		)
		.else_(0)
	).as_("is_half_day")

	query = (
		frappe.qb.from_(LeaveApplication)
		.inner_join(LeaveType)
		.on((LeaveType.name == LeaveApplication.leave_type))
		.select(
			LeaveType.name,
			LeaveType.is_ppl,
			LeaveType.fraction_of_daily_salary_per_leave,
			(is_half_day),
		)
		.where(
			(((LeaveType.is_lwp == 1) | (LeaveType.is_ppl == 1)))
			& (LeaveApplication.docstatus == 1)
			& (LeaveApplication.status == "Approved")
			& (LeaveApplication.employee == employee)
			& ((LeaveApplication.salary_slip.isnull()) | (LeaveApplication.salary_slip == ""))
			& ((LeaveApplication.from_date <= date) & (date <= LeaveApplication.to_date))
		)
	)

	if date in holidays:
		query = query.where((LeaveType.include_holiday == "1"))

	return query.run(as_dict=True)


def get_salary_slip_totals(employee, fiscal_year):
	"""
	Récupère les totaux des fiches de paie d'un employé pour un exercice fiscal.
	"""
	results = frappe.db.sql(
		"""
		SELECT
			COUNT(*) as count,
			SUM(net_pay) as total_net_pay,
			SUM(gross_pay) as total_gross_pay
		FROM `tabSalary Slip`
		WHERE employee = %s
			AND fiscal_year = %s
			AND docstatus = 1
		""",
		(employee, fiscal_year),
		as_dict=True,
	)
	return results[0] if results else {}
