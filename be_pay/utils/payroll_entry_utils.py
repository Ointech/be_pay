# Copyright (c) 2025, Be Pay
# License: MIT

import frappe
from frappe import _
from frappe.utils import getdate, add_months, get_last_day


@frappe.whitelist()
def get_payroll_period_mode():
	return {
		"use_payroll_period_by_employment_type": frappe.db.get_single_value(
			"Pay Payroll Settings",
			"use_payroll_period_by_employment_type"
		)
	}


@frappe.whitelist()
def get_dates_by_employment_type(employment_type=None, company=None, payroll_period=None):
	"""
	Calcule start_date et end_date pour Payroll Entry selon la configuration
	Be Pay (day_start / day_end par Employment Type + Company).

	Si la config Be Pay est desactivee, renvoie les dates du Payroll Period natif.
	"""
	if not payroll_period:
		frappe.throw(_("Payroll Period is required"))

	settings = frappe.get_single("Pay Payroll Settings")
	use_be_pay = settings.use_payroll_period_by_employment_type

	if not use_be_pay:
		# Mode natif : recuperer directement les dates du Payroll Period
		pp = frappe.db.get_value(
			"Payroll Period",
			payroll_period,
			["start_date", "end_date"],
			as_dict=True
		)
		if not pp:
			frappe.throw(_("Payroll Period not found"))
		return {
			"start_date": str(pp.start_date),
			"end_date": str(pp.end_date)
		}

	# Mode Be Pay : calcul dynamique depuis day_start / day_end
	if not employment_type:
		frappe.throw(_("Employment Type is required when 'Use Payroll Period by Employment Type' is enabled"))

	config = None
	for row in settings.payroll_period_details:
		if row.employment_type == employment_type and row.company == company:
			config = row
			break

	if not config:
		frappe.throw(
			_("No Payroll Period configuration found for Employment Type: {0} and Company: {1}").format(
				employment_type, company
			)
		)

	# Mois/annee de base depuis le Payroll Period selectionne
	pp_start = frappe.db.get_value("Payroll Period", payroll_period, "start_date")
	if not pp_start:
		frappe.throw(_("Payroll Period not found"))

	base = getdate(pp_start)
	year = base.year
	month = base.month

	day_start = int(config.day_start or 1)
	day_end = int(config.day_end or 31)

	# Calcul start_date
	if day_start <= day_end:
		# Periode dans un seul mois (ex: 1 -> 31)
		start_date = _safe_date(year, month, day_start)
		end_date = _safe_date(year, month, day_end)
	else:
		# Periode chevauche deux mois (ex: 21 -> 20)
		# start_date = day_start du mois precedent
		# end_date = day_end du mois en cours
		start_month = month - 1 if month > 1 else 12
		start_year = year if month > 1 else year - 1
		start_date = _safe_date(start_year, start_month, day_start)
		end_date = _safe_date(year, month, day_end)

	return {
		"start_date": str(start_date),
		"end_date": str(end_date)
	}


def _safe_date(year, month, day):
	"""Construit une date en ajustant le jour si hors limites du mois."""
	from datetime import date
	last = get_last_day(date(year, month, 1))
	if day > last.day:
		day = last.day
	return date(year, month, day)
