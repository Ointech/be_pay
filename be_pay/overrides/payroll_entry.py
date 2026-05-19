# Copyright (c) 2025, Be Pay
# License: MIT

import frappe
from frappe import _

from hrms.payroll.doctype.payroll_entry.payroll_entry import (
	PayrollEntry,
	get_employee_list,
)


class CustomPayrollEntry(PayrollEntry):
	def make_filters(self):
		filters = super().make_filters()
		filters["employment_type"] = self.get("employment_type")
		return filters

	def fill_employee_details(self):
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
