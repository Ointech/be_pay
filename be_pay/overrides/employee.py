# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Employee pour Be Pay.

Intègre la gestion des catégories, de l'ancienneté et des analytiques.
"""

import frappe
from frappe import _
from erpnext.setup.doctype.employee.employee import Employee


class CustomEmployee(Employee):
    """
    Extension de la classe Employee pour la logique Be Pay.
    """

    def validate(self):
        """
        Validation Be Pay : analytiques à 100%, majuscules, etc.
        """
        self._be_pay_validate_analytiques()
        self._be_pay_force_uppercase_names()
        self._be_pay_calculate_anciennete()
        super().validate()

    def before_save(self):
        """
        Avant sauvegarde : mise à jour des champs calculés Be Pay.
        """
        self._be_pay_update_cost_center()
        self._be_pay_sync_category_salary()
        super().before_save()

    def _be_pay_validate_analytiques(self):
        """
        Vérifie que le total des pourcentages analytiques est égal à 100.
        """
        if not hasattr(self, "custom_analytiques") or not self.custom_analytiques:
            return

        total = sum(
            float(row.pourcentage or 0)
            for row in self.custom_analytiques
        )

        if total != 100:
            frappe.throw(
                _("Le pourcentage des analytiques doit être égal à 100 !!!!")
            )

    def _be_pay_force_uppercase_names(self):
        """
        Force les noms en majuscules.
        """
        if self.first_name:
            self.first_name = self.first_name.upper()
        if self.middle_name:
            self.middle_name = self.middle_name.upper()
        if self.last_name:
            self.last_name = self.last_name.upper()
        if self.employee_name:
            self.employee_name = self.employee_name.upper()

    def _be_pay_calculate_anciennete(self):
        """
        Calcule et met à jour l'ancienneté de l'employé.
        """
        if not self.date_of_joining or self.status != "Active":
            return

        from be_pay.utils.payroll_utils import calculate_anciennete

        self.anciennete = calculate_anciennete(self.date_of_joining)

    def _be_pay_update_cost_center(self):
        """
        Met à jour la description du centre de coûts.
        """
        if self.payroll_cost_center:
            self.custom_cost_center_description = self.payroll_cost_center

    def _be_pay_sync_category_salary(self):
        """
        Synchronise le salaire de base depuis la catégorie d'employé.
        """
        if not self.employee_category_details:
            return

        from be_pay.utils.payroll_utils import get_employee_category_salary

        salary_per_day = get_employee_category_salary(self.employee_category_details)
        if salary_per_day is not None:
            self.pay_basic_salary_per_day = salary_per_day


def get_employee_full_name(employee_id):
    """
    Récupère le nom complet formaté d'un employé.

    Args:
        employee_id (str): ID de l'employé

    Returns:
        str: Nom complet
    """
    employee = frappe.db.get_value(
        "Employee",
        employee_id,
        ["first_name", "middle_name", "last_name"],
        as_dict=True
    )

    if not employee:
        return ""

    parts = [
        employee.first_name or "",
        employee.middle_name or "",
        employee.last_name or ""
    ]

    return " ".join(p for p in parts if p).strip()
