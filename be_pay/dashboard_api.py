import frappe
from frappe.utils import getdate


@frappe.whitelist()
def get_leave_years():
	"""Retourne la liste des années distinctes des Leave Applications."""
	years = frappe.db.sql(
		"""
		SELECT DISTINCT YEAR(from_date) as year
		FROM `tabLeave Application`
		WHERE docstatus < 2
		ORDER BY year DESC
		""",
		as_dict=True,
	)
	if not years:
		return [{"year": getdate().year}]
	return years


@frappe.whitelist()
def get_leave_types():
	"""Retourne la liste des types de congés actifs."""
	return frappe.get_all("Leave Type", filters={}, fields=["name"], order_by="name")


@frappe.whitelist()
def get_leave_dashboard_data(year=None, status="All", leave_type="All"):
	"""
	Retourne les données agrégées des leave applications par designation et employé.
	"""
	filters = {"docstatus": ["<", 2]}

	if year:
		filters["from_date"] = ["between", [f"{year}-01-01", f"{year}-12-31"]]

	if status != "All":
		filters["status"] = status

	if leave_type != "All":
		filters["leave_type"] = leave_type

	leaves = frappe.get_all(
		"Leave Application",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"leave_type",
			"status",
			"total_leave_days",
			"from_date",
		],
	)

	employees = list(set([l.employee for l in leaves if l.employee]))
	employee_map = {}
	if employees:
		emp_data = frappe.get_all(
			"Employee",
			filters={"name": ["in", employees]},
			fields=["name", "designation"],
		)
		employee_map = {e.name: (e.designation or "Non défini") for e in emp_data}

	designation_stats = {}
	employee_stats = {}

	for leave in leaves:
		designation = employee_map.get(leave.employee, "Non défini")
		emp_key = (designation, leave.employee)

		if designation not in designation_stats:
			designation_stats[designation] = {
				"designation": designation,
				"total_requests": 0,
				"total_days": 0,
				"approved_days": 0,
				"pending_days": 0,
				"rejected_days": 0,
			}
		designation_stats[designation]["total_requests"] += 1
		designation_stats[designation]["total_days"] += leave.total_leave_days or 0
		if leave.status == "Approved":
			designation_stats[designation]["approved_days"] += leave.total_leave_days or 0
		elif leave.status == "Open":
			designation_stats[designation]["pending_days"] += leave.total_leave_days or 0
		elif leave.status == "Rejected":
			designation_stats[designation]["rejected_days"] += leave.total_leave_days or 0

		if emp_key not in employee_stats:
			employee_stats[emp_key] = {
				"designation": designation,
				"employee": leave.employee,
				"employee_name": leave.employee_name or leave.employee,
				"total_requests": 0,
				"total_days": 0,
				"approved_days": 0,
				"pending_days": 0,
				"rejected_days": 0,
			}
		employee_stats[emp_key]["total_requests"] += 1
		employee_stats[emp_key]["total_days"] += leave.total_leave_days or 0
		if leave.status == "Approved":
			employee_stats[emp_key]["approved_days"] += leave.total_leave_days or 0
		elif leave.status == "Open":
			employee_stats[emp_key]["pending_days"] += leave.total_leave_days or 0
		elif leave.status == "Rejected":
			employee_stats[emp_key]["rejected_days"] += leave.total_leave_days or 0

	designation_list = sorted(
		designation_stats.values(),
		key=lambda x: x["total_requests"],
		reverse=True,
	)
	employee_list = sorted(
		employee_stats.values(),
		key=lambda x: (x["designation"], x["total_requests"]),
		reverse=False,
	)

	totals = {
		"total_requests": len(leaves),
		"total_days": sum(l.total_leave_days or 0 for l in leaves),
		"approved_days": sum(
			(l.total_leave_days or 0) for l in leaves if l.status == "Approved"
		),
		"pending_days": sum(
			(l.total_leave_days or 0) for l in leaves if l.status == "Open"
		),
		"rejected_days": sum(
			(l.total_leave_days or 0) for l in leaves if l.status == "Rejected"
		),
	}

	return {
		"designations": designation_list,
		"employees": employee_list,
		"totals": totals,
	}
