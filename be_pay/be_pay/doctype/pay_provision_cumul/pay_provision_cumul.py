# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class PayProvisionCumul(Document):
    def before_save(self):
        self._calculate_leave_report()

    def _calculate_leave_report(self):
        """
        Si Value Leave Report n'est pas renseigné, le calculer automatiquement
        à partir de Value Ratio Report et du salaire de base (CTC) de l'employé.
        """
        if not self.value_leave_report and self.value_ratio_report and self.employee:
            base_salary = frappe.db.get_value("Employee", self.employee, "ctc") or 0
            working_day = flt(
                frappe.db.get_single_value("Pay Payroll Settings", "working_day") or 26
            )
            if base_salary and working_day:
                self.value_leave_report = (
                    flt(self.value_ratio_report) * flt(base_salary) / working_day
                )
