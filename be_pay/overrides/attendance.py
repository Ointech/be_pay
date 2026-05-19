# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Attendance pour Be Pay.

Gère la génération du naming series personnalisé et la création
automatique des présences pour les jours fériés.
"""

import frappe
from frappe import _
from hrms.hr.doctype.attendance.attendance import Attendance


class CustomAttendance(Attendance):
    """
    Extension de la classe Attendance pour la logique Be Pay.
    """

    def before_insert(self):
        """
        Avant insertion : génération du naming series personnalisé.
        """
        self._be_pay_set_custom_naming_series()
        super().before_insert()

    def before_save(self):
        """
        Avant sauvegarde : création des présences pour jours fériés antérieurs.
        """
        self._be_pay_create_holiday_attendance()
        # Attendance (HRMS) ne définit pas before_save ; inutile d'appeler super()

    def _be_pay_set_custom_naming_series(self):
        """
        Génère un naming series au format : AA-EMP-YYYY-MM-JJ
        """
        if not self.attendance_date or not self.employee:
            return

        to_date = frappe.utils.getdate(self.attendance_date)
        current_day = f"{to_date.day:02d}"
        current_month = f"{to_date.month:02d}"
        current_year = to_date.year
        current_year_deux = str(current_year)[-2:]

        naming = f"{current_year_deux}-{self.employee}-{current_year}-{current_month}-{current_day}"
        self.naming_series = naming
        self.name = naming

    def _be_pay_create_holiday_attendance(self):
        """
        Crée les présences pour les 7 jours précédents si jours fériés.
        """
        if getattr(frappe.local, "_be_pay_creating_holiday_attendance", False):
            return

        frappe.local._be_pay_creating_holiday_attendance = True
        try:
            if not self.attendance_date or not self.employee:
                return

            to_date = frappe.utils.getdate(self.attendance_date)
            current_date = frappe.utils.add_days(to_date, -7)

            while current_date < to_date:
                holidays = frappe.db.sql(
                    """
                    SELECT * FROM `tabHoliday`
                    WHERE holiday_date = %s AND weekly_off = 1
                    """,
                    (current_date,),
                    as_dict=True
                )

                if holidays:
                    existing = frappe.db.sql(
                        """
                        SELECT * FROM `tabAttendance`
                        WHERE attendance_date = %s AND employee = %s
                        """,
                        (holidays[0].holiday_date, self.employee),
                        as_dict=True
                    )

                    if not existing:
                        attendance = frappe.new_doc("Attendance")
                        attendance.employee = self.employee
                        attendance.employee_name = self.employee_name
                        attendance.status = "Present"
                        attendance.attendance_date = current_date
                        attendance.company = self.company
                        attendance.department = self.department
                        attendance.shift = "O"
                        attendance.save()
                        attendance.submit()

                current_date = frappe.utils.add_days(current_date, 1)
        finally:
            frappe.local._be_pay_creating_holiday_attendance = False


def get_attendance_summary_for_period(employee, from_date, to_date):
    """
    Récupère le résumé des présences pour une période donnée.

    Args:
        employee (str): ID de l'employé
        from_date (date or str): Date de début
        to_date (date or str): Date de fin

    Returns:
        dict: Résumé des présences
    """
    results = frappe.db.sql(
        """
        SELECT
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN status = 'On Leave' THEN 1 ELSE 0 END) as leave_days,
            SUM(CASE WHEN status = 'Half Day' THEN 1 ELSE 0 END) as half_days
        FROM `tabAttendance`
        WHERE employee = %s
            AND attendance_date BETWEEN %s AND %s
            AND docstatus = 1
        """,
        (employee, from_date, to_date),
        as_dict=True
    )

    return results[0] if results else {}
