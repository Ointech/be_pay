# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days
from collections import defaultdict


@frappe.whitelist()
def get_allowed_salary_components():
	"""
	Retourne la liste des salary_components autorisés
	depuis Pay Payroll Settings > attendance_salary_components.
	"""
	settings = frappe.get_single("Pay Payroll Settings")
	allowed = []
	for row in settings.attendance_salary_components or []:
		if row.salary_component:
			allowed.append(row.salary_component)
	return allowed


class PayAttendanceList(Document):
	def validate(self):
		self._validate_unique_period()

	def before_save(self):
		frappe.msgprint("before_save appelé")
		self.calculate_lines()

	def calculate_lines(self):
		"""
		Calcule pour chaque employé du PAL :
		- Heures supplémentaires (depuis Attendance.hours_control) réparties
		  dans les champs dynamiques selon Be Pay Overtime Rule.
		- Absences (jours sans Attendance, Leave, Holiday ni Attendance Request).
		"""
		try:
			self._calculate_lines_core()
		except Exception:
			frappe.log_error(
				title="Pay Attendance List - Erreur calculate_lines",
				message=frappe.get_traceback(),
			)
			raise

	def _calculate_lines_core(self):
		frappe.msgprint("calculate_lines démarrée...")
		if not self.company or not self.start_date or not self.end_date:
			frappe.msgprint(
				f"calculate_lines abortée : company={self.company} start={self.start_date} end={self.end_date}",
				alert=True,
			)
			return

		# ------------------------------------------------------------------
		# 1. Règles HS
		# ------------------------------------------------------------------
		rules = frappe.get_all(
			"Be Pay Overtime Rule",
			filters={"company": self.company, "active": 1},
			fields=["target_fieldname", "is_holiday_rule", "from_hours", "to_hours"],
			order_by="from_hours asc",
		)

		# ------------------------------------------------------------------
		# 2. Employés concernés
		# ------------------------------------------------------------------
		emp_filters = {"company": self.company, "status": "Active"}
		if self.employment_type:
			emp_filters["employment_type"] = self.employment_type
		employees = frappe.get_all(
			"Employee",
			filters=emp_filters,
			fields=["name", "employee_name", "employment_type", "holiday_list"],
		)

		if not employees:
			self.attendance_line = []
			return

		# ------------------------------------------------------------------
		# 3. Préchargement des données de la période
		# ------------------------------------------------------------------
		start = getdate(self.start_date)
		end = getdate(self.end_date)

		# Toutes les dates de la période
		period_dates = []
		d = start
		while d <= end:
			period_dates.append(d)
			d = add_days(d, 1)
		period_set = set(period_dates)

		# Attendances
		all_attendances = frappe.get_all(
			"Attendance",
			filters={
				"attendance_date": ["between", [self.start_date, self.end_date]],
				"docstatus": 1,
			},
			fields=["employee", "attendance_date", "hours_control", "shift"],
		)
		att_by_emp = defaultdict(list)
		for a in all_attendances:
			att_by_emp[a.employee].append(a)

		# Leave Applications approuvées
		all_leaves = frappe.get_all(
			"Leave Application",
			filters={
				"docstatus": 1,
				"status": "Approved",
				"from_date": ["<=", self.end_date],
				"to_date": [">=", self.start_date],
			},
			fields=["employee", "from_date", "to_date"],
		)
		leave_by_emp = defaultdict(list)
		for la in all_leaves:
			leave_by_emp[la.employee].append(la)

		# Attendance Requests
		all_requests = frappe.get_all(
			"Attendance Request",
			filters={
				"docstatus": 1,
				"from_date": ["<=", self.end_date],
				"to_date": [">=", self.start_date],
			},
			fields=["employee", "from_date", "to_date"],
		)
		request_by_emp = defaultdict(list)
		for ar in all_requests:
			request_by_emp[ar.employee].append(ar)

		# Holiday lists
		company_holiday_list = frappe.db.get_value(
			"Company", self.company, "default_holiday_list"
		)
		emp_holiday_lists = {}
		unique_hol_lists = set()
		for emp in employees:
			hl = emp.holiday_list or company_holiday_list
			emp_holiday_lists[emp.name] = hl
			if hl:
				unique_hol_lists.add(hl)

		# Holidays par liste
		holidays_by_list = defaultdict(set)
		if unique_hol_lists:
			for h in frappe.get_all(
				"Holiday",
				filters={
					"parent": ["in", list(unique_hol_lists)],
					"holiday_date": ["between", [self.start_date, self.end_date]],
				},
				fields=["parent", "holiday_date"],
			):
				holidays_by_list[h.parent].add(getdate(h.holiday_date))

		# Holiday list par shift (via Shift Type)
		all_shifts = {a.shift for a in all_attendances if a.shift}
		shift_holiday_lists = {}
		for shift in all_shifts:
			shift_holiday_lists[shift] = frappe.db.get_value(
				"Shift Type", shift, "holiday_list"
			)

		# ------------------------------------------------------------------
		# 4. Traitement employé par employé
		# ------------------------------------------------------------------
		self.attendance_line = []

		for emp in employees:
			employee = emp.name
			attendances = att_by_emp.get(employee, [])

			# --- Absences ---
			covered_dates = set()
			for a in attendances:
				covered_dates.add(getdate(a.attendance_date))

			for la in leave_by_emp.get(employee, []):
				d = getdate(la.from_date)
				while d <= getdate(la.to_date):
					if d in period_set:
						covered_dates.add(d)
					d = add_days(d, 1)

			for ar in request_by_emp.get(employee, []):
				d = getdate(ar.from_date)
				while d <= getdate(ar.to_date):
					if d in period_set:
						covered_dates.add(d)
					d = add_days(d, 1)

			emp_hl = emp_holiday_lists.get(employee)
			for hd in holidays_by_list.get(emp_hl, []):
				covered_dates.add(hd)

			absence_days = 0
			for pd in period_dates:
				if pd not in covered_dates:
					absence_days += 1

			# --- Heures supplémentaires ---
			total_holiday_hours = 0.0
			total_normal_hours = 0.0

			for a in attendances:
				ad = getdate(a.attendance_date)
				is_hol = False

				# Vérifier via le shift
				shift_hl = shift_holiday_lists.get(a.shift)
				if shift_hl:
					is_hol = ad in holidays_by_list.get(shift_hl, set())

				# Fallback via employee holiday list
				if not is_hol and emp_hl:
					is_hol = ad in holidays_by_list.get(emp_hl, set())

				if is_hol:
					total_holiday_hours += flt(a.hours_control)
				else:
					total_normal_hours += flt(a.hours_control)

			# --- Construction de la ligne ---
			line_data = {
				"employee": employee,
				"employee_name": emp.employee_name or "",
				"employment_type": emp.employment_type or "",
				"absence": absence_days,
			}

			# Règles fériés
			holiday_rules = [r for r in rules if r.is_holiday_rule]
			if holiday_rules and total_holiday_hours > 0:
				line_data[holiday_rules[0].target_fieldname] = total_holiday_hours

			# Règles normales
			normal_rules = [r for r in rules if not r.is_holiday_rule]
			if normal_rules and total_normal_hours > 0:
				for rule in normal_rules:
					from_h = flt(rule.from_hours)
					to_h = flt(rule.to_hours)
					if to_h == 0:
						to_h = 999999
					if from_h <= total_normal_hours <= to_h:
						line_data[rule.target_fieldname] = total_normal_hours
						break

			# On ajoute la ligne si elle contient au moins une donnée
			has_data = (
				absence_days > 0
				or total_holiday_hours > 0
				or total_normal_hours > 0
			)
			if has_data:
				self.append("attendance_line", line_data)

		frappe.logger().info(
			"PAL %s | calculate_lines terminée : %s lignes créées",
			self.name, len(self.attendance_line or [])
		)

	def _validate_unique_period(self):
		"""Vérifie qu'il n'existe pas déjà un PAL pour la même période + société + type."""
		if not self.pay_period or not self.company:
			return

		filters = {
			"pay_period": self.pay_period,
			"company": self.company,
			"name": ("!=", self.name),
		}
		if self.employment_type:
			filters["employment_type"] = self.employment_type

		filters["docstatus"] = ("!=", 2)
		existing = frappe.get_all(
			"Pay Attendance List",
			filters=filters,
			fields=["name"],
			limit=1,
		)
		if existing:
			frappe.throw(
				_(
					"Un Pay Attendance List existe déjà pour cette période ({0}), "
					"société ({1}) et type d'emploi ({2})."
				).format(
					self.pay_period,
					self.company,
					self.employment_type or "Non spécifié",
				)
			)
