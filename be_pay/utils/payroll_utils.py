# Copyright (c) 2025, Be Pay
# License: MIT

"""
Utilitaires de paie pour Be Pay.

Fonctions helpers pour le calcul de l'ancienneté, des provisions,
et des éléments de paie spécifiques.
"""

import frappe
from frappe import _


def calculate_anciennete(date_of_joining, reference_date=None):
    """
    Calcule l'ancienneté en années à partir de la date d'embauche.

    Args:
        date_of_joining (date or str): Date d'embauche
        reference_date (date or str, optional): Date de référence. Par défaut now().

    Returns:
        int: Nombre d'années d'ancienneté
    """
    if not date_of_joining:
        return 0

    date_entree = frappe.utils.getdate(date_of_joining)
    date_actuelle = frappe.utils.getdate(reference_date) if reference_date else frappe.utils.nowdate()
    date_actuelle = frappe.utils.getdate(date_actuelle)

    anciennete = date_actuelle.year - date_entree.year

    if date_actuelle.month < date_entree.month or (
        date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day
    ):
        anciennete = anciennete - 1

    return anciennete


def calculate_months_between(start_date, end_date):
    """
    Calcule le nombre de mois entre deux dates.

    Args:
        start_date (date or str): Date de début
        end_date (date or str): Date de fin

    Returns:
        int: Nombre de mois
    """
    start = frappe.utils.getdate(start_date)
    end = frappe.utils.getdate(end_date)

    months = (end.year - start.year) * 12 + (end.month - start.month)

    if end.day < start.day:
        months = months - 1

    return months


def get_employee_category_salary(employee_category_details):
    """
    Récupère le salaire de base journalier d'une catégorie d'employé.

    Args:
        employee_category_details (str): Nom de la catégorie

    Returns:
        float or None: Salaire de base journalier
    """
    if not employee_category_details:
        return None

    return frappe.db.get_value(
        "Pay Employee Category Detail",
        employee_category_details,
        "basic_salary_per_day"
    )


def get_attendance_summary(pay_period, employee):
    """
    Récupère le résumé des présences pour une période de paie et un employé.

    Args:
        pay_period (str): Période de paie
        employee (str): ID de l'employé

    Returns:
        dict or None: Résumé des présences
    """
    if not pay_period or not employee:
        return None

    results = frappe.db.sql(
        """
        SELECT
            s.pay_hours_30 AS hours_30,
            s.pay_hours_60 AS hours_60,
            s.pay_sunday_hours AS sunday_hours,
            s.pay_night_hours AS night_hours,
            s.absence,
            s.absences,
            s.pay_absence,
            s.hours,
            s.days,
            s.custom_hs_130,
            s.custom_hs_160,
            s.custom_hs_ferie,
            s.is_overtime_line
        FROM
            `tabPay Attendance Line` s
        INNER JOIN
            `tabPay Attendance List` d ON d.name = s.parent
        WHERE
            d.pay_period = %s
            AND s.employee = %s
            AND s.docstatus = 1
        """,
        (pay_period, employee),
        as_dict=True
    )

    return results[0] if results else None


def get_leave_taken(employee, start_date, end_date):
    """
    Récupère les jours de congé pris par type pour un employé sur une période.

    Args:
        employee (str): ID de l'employé
        start_date (date or str): Date de début
        end_date (date or str): Date de fin

    Returns:
        list: Liste des congés par type
    """
    return frappe.db.sql(
        """
        SELECT
            s.leave_type,
            SUM(
                DATEDIFF(
                    LEAST(s.to_date, %(end_date)s),
                    GREATEST(s.from_date, %(start_date)s)
                ) + 1
            ) AS total_leave_days
        FROM `tabLeave Application` s
        WHERE s.employee = %(employee)s
            AND s.docstatus = 1
            AND (
                s.from_date <= %(end_date)s AND s.to_date >= %(start_date)s
            )
        GROUP BY s.leave_type;
        """,
        {
            "employee": employee,
            "start_date": frappe.utils.getdate(start_date),
            "end_date": frappe.utils.getdate(end_date),
        },
        as_dict=True
    )


@frappe.whitelist()
def get_employee_bank_info(employee):
    """
    API : Récupère les informations bancaires d'un employé.

    Args:
        employee (str): ID de l'employé

    Returns:
        dict: Informations bancaires
    """
    if not employee:
        return {}

    emp = frappe.db.get_value(
        "Employee",
        employee,
        ["local_bank", "bank_name", "bank_ac_no"],
        as_dict=True
    )

    return emp or {}
