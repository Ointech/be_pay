# Copyright (c) 2026, Be Pay and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday


def get_active_overtime_rules(company):
	"""Retourne toutes les règles actives d'heures sup pour une company."""
	return frappe.get_all(
		"Be Pay Overtime Rule",
		filters={"company": company, "active": 1},
		fields=["*"],
		order_by="from_hours asc",
	)


def is_attendance_on_holiday(attendance):
	"""Vérifie si une Attendance tombe sur un jour férié (via Shift Type -> Holiday List)."""
	if not attendance.get("shift"):
		return False

	holiday_list = frappe.db.get_value("Shift Type", attendance.shift, "holiday_list")
	if not holiday_list:
		return False

	return is_holiday(holiday_list, attendance.attendance_date)


def get_shift_normal_hours(shift_name):
	"""Retourne les heures normales du shift (champ nombre_heure)."""
	if not shift_name:
		return 0
	return flt(frappe.db.get_value("Shift Type", shift_name, "nombre_heure")) or 0


def distribute_overtime_for_attendance(attendance, rules):
	"""
	Calcule les heures sup d'une Attendance et les répartit selon les règles.

	Retourne un dict {target_fieldname: hours}.
	"""
	working_hours = flt(attendance.get("working_hours"))
	if working_hours <= 0:
		return {}

	on_holiday = is_attendance_on_holiday(attendance)

	# Jour férié : toutes les heures travaillées sont considérées comme HS majorées
	if on_holiday:
		overtime_hours = max(0, working_hours)
	else:
		shift_hours = get_shift_normal_hours(attendance.get("shift"))
		overtime_hours = max(0, working_hours - shift_hours)

	if overtime_hours <= 0:
		return {}

	result = {}
	for rule in rules:
		if rule.is_holiday_rule != on_holiday:
			continue

		lower = flt(rule.from_hours)
		upper = flt(rule.to_hours) if rule.to_hours else 999999

		if overtime_hours > lower:
			hours_in_tranche = max(0, min(overtime_hours, upper) - lower)
			if hours_in_tranche > 0:
				result[rule.target_fieldname] = flt(hours_in_tranche, 2)

	return result


def get_overtime_settings(company):
	"""Retourne les paramètres globaux de calcul des HS."""
	return frappe.db.get_value(
		"Be Pay Overtime Settings",
		{"company": company},
		["standard_daily_hours", "name"],
		as_dict=True,
	)
