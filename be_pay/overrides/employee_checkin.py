# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Employee Checkin pour Be Pay.

Gère l'assignation automatique des shifts (Morning/Night) en fonction
de l'heure de pointage.
"""

import frappe
from frappe import _
from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin


class CustomEmployeeCheckin(EmployeeCheckin):
    """
    Extension de la classe Employee Checkin pour la logique Be Pay.
    """

    def before_save(self):
        """
        Avant sauvegarde : assignation automatique du shift.
        """
        self._be_pay_auto_assign_shift()
        super().before_save()

    def _be_pay_auto_assign_shift(self):
        """
        Assigne automatiquement le shift en fonction de l'heure de pointage.
        """
        if not self.time or self.shift:
            return

        punch = str(self.time).split(" ")[1]
        punchdate = str(self.time).split(" ")[0]
        hour = int(punch.split(":")[0])
        log_type = self.log_type

        # Plages horaires
        morning_in = range(5, 12)
        night_in = range(16, 22)
        morning_out = range(16, 23)
        night_out = range(7, 12)

        # Configuration des shifts
        shift_configs = {
            "Morning": {
                "start_time": punchdate + " 08:00:01",
                "end_time": punchdate + " 18:00:00",
                "actual_start": punchdate + " 06:00:00",
                "actual_end": punchdate + " 22:00:00",
            },
            "Night": {
                "start_time": punchdate + " 18:00:01",
                "end_time": punchdate + " 08:00:00",
                "actual_start": punchdate + " 16:00:00",
                "actual_end": punchdate + " 12:00:00",
            }
        }

        assigned_shift = None

        if log_type == "IN" and hour in morning_in:
            assigned_shift = "Morning"
        elif log_type == "IN" and hour in night_in:
            assigned_shift = "Night"
        elif log_type == "OUT" and hour in morning_out:
            assigned_shift = "Morning"
        elif log_type == "OUT" and hour in night_out:
            assigned_shift = "Night"

        if assigned_shift:
            config = shift_configs[assigned_shift]

            self.shift = assigned_shift

            if assigned_shift == "Night" and log_type == "OUT":
                self.shift_start = frappe.utils.add_to_date(
                    frappe.utils.get_datetime(config["start_time"]), days=-1
                )
                self.shift_actual_start = frappe.utils.add_to_date(
                    frappe.utils.get_datetime(config["actual_start"]), days=-1
                )
            else:
                self.shift_start = frappe.utils.get_datetime(config["start_time"])
                self.shift_actual_start = frappe.utils.get_datetime(config["actual_start"])

            self.shift_end = frappe.utils.get_datetime(config["end_time"])
            self.shift_actual_end = frappe.utils.get_datetime(config["actual_end"])


def get_employee_checkins_for_date(employee, checkin_date):
    """
    Récupère les pointages d'un employé pour une date donnée.

    Args:
        employee (str): ID de l'employé
        checkin_date (date or str): Date de pointage

    Returns:
        list: Liste des pointages
    """
    return frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": employee,
            "time": ["between", [
                f"{checkin_date} 00:00:00",
                f"{checkin_date} 23:59:59"
            ]]
        },
        fields=["name", "log_type", "time", "shift"],
        order_by="time asc"
    )
