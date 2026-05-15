# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Leave Application pour Be Pay.

Gère le calcul des jours de congé avec jours off et la création
automatique des enregistrements de présence.
"""

import frappe
from frappe import _
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication


class CustomLeaveApplication(LeaveApplication):
    """
    Extension de la classe Leave Application pour la logique Be Pay.
    """

    def validate(self):
        """
        Validation Be Pay : calcul des jours de congé avec jours off.
        """
        self._be_pay_calculate_leave_days()
        super().validate()

    def before_submit(self):
        """
        Avant soumission : recalcul des jours de congé.
        """
        self._be_pay_calculate_leave_days()
        super().before_submit()

    def on_submit(self):
        """
        Après soumission : création automatique des attendances.
        """
        self._be_pay_create_attendance_records()
        super().on_submit()

    def _be_pay_calculate_leave_days(self):
        """
        Calcule le nombre de jours de congé en soustrayant les jours off.
        """
        if not self.from_date or not self.to_date:
            return

        start_date = frappe.utils.getdate(self.from_date)
        end_date = frappe.utils.getdate(self.to_date)

        total_days = (end_date - start_date).days + 1

        valid_days_off = 0
        if hasattr(self, "custom_jours_off") and self.custom_jours_off:
            for row in self.custom_jours_off:
                if row.date_day_off:
                    row_date = frappe.utils.getdate(row.date_day_off)
                    if start_date <= row_date <= end_date:
                        valid_days_off += 1

        self.total_leave_days = total_days - valid_days_off

    def _be_pay_create_attendance_records(self):
        """
        Crée les enregistrements de présence (On Leave) pour chaque jour.
        """
        if not self.from_date or not self.to_date or not self.employee:
            return

        from_date = frappe.utils.getdate(self.from_date)
        to_date = frappe.utils.getdate(self.to_date)
        current_date = from_date

        attendance_records = []

        while current_date <= to_date:
            # Vérifier s'il y a un jour férié
            holiday_results = frappe.db.sql(
                """
                SELECT * FROM `tabHoliday`
                WHERE holiday_date = %s AND weekly_off = 1
                """,
                (current_date,),
                as_dict=True
            )

            # Vérifier si un attendance existe déjà
            attendance_exists = frappe.db.sql(
                """
                SELECT name FROM `tabAttendance`
                WHERE employee = %s AND attendance_date = %s
                """,
                (self.employee, current_date),
                as_dict=True
            )

            if attendance_exists:
                frappe.msgprint(
                    _(
                        "L'assiduité pour l'employé {0} est déjà marquée pour la date {1}."
                    ).format(self.employee, current_date)
                )
            else:
                attendance = frappe.new_doc("Attendance")
                attendance.employee = self.employee
                attendance.employee_name = self.employee_name
                attendance.status = "On Leave"
                attendance.leave_type = self.leave_type
                attendance.shift = self.leave_type
                attendance.leave_application = self.name
                attendance.attendance_date = current_date
                attendance.company = self.company
                attendance.department = self.department

                attendance_records.append(attendance)

            current_date = frappe.utils.add_days(current_date, 1)

        for attendance in attendance_records:
            attendance.save()
            attendance.submit()

        if attendance_records:
            frappe.msgprint(
                _("Tous les enregistrements de présence ont été créés avec succès.")
            )


def get_leave_balance_by_type(employee, leave_type, from_date, to_date):
    """
    Récupère le solde de congés pour un type donné sur une période.

    Args:
        employee (str): ID de l'employé
        leave_type (str): Type de congé
        from_date (date or str): Date de début
        to_date (date or str): Date de fin

    Returns:
        dict: Solde de congés
    """
    results = frappe.db.sql(
        """
        SELECT
            SUM(total_leave_days) as total_taken,
            COUNT(*) as application_count
        FROM `tabLeave Application`
        WHERE employee = %s
            AND leave_type = %s
            AND docstatus = 1
            AND from_date >= %s
            AND to_date <= %s
        """,
        (employee, leave_type, from_date, to_date),
        as_dict=True
    )

    return results[0] if results else {"total_taken": 0, "application_count": 0}
