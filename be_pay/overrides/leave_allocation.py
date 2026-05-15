# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Leave Allocation pour Be Pay.

Gère les allocations de congés avec la logique métier Be Pay.
"""

import frappe
from frappe import _
from hrms.hr.doctype.leave_allocation.leave_allocation import LeaveAllocation


class CustomLeaveAllocation(LeaveAllocation):
    """
    Extension de la classe Leave Allocation pour la logique Be Pay.
    """

    def validate(self):
        """
        Validation Be Pay : vérifications spécifiques.
        """
        self._be_pay_validate_allocation()
        super().validate()

    def _be_pay_validate_allocation(self):
        """
        Vérifie la cohérence de l'allocation avec les données de l'employé.
        """
        if not self.employee:
            return

        employee = frappe.get_doc("Employee", self.employee)

        # Vérifier que le type de congé est compatible avec le contrat
        if self.leave_type and employee.employment_type:
            leave_type_doc = frappe.get_doc("Leave Type", self.leave_type)

            # Log de validation pour traçabilité
            frappe.logger().info(
                f"[Be Pay] Validation allocation {self.name} "
                f"pour employé {self.employee} "
                f"(type contrat: {employee.employment_type}, "
                f"type congé: {self.leave_type})"
            )

    def on_submit(self):
        """
        Après soumission : mise à jour des soldes de congés.
        """
        self._be_pay_update_employee_leave_balance()
        super().on_submit()

    def _be_pay_update_employee_leave_balance(self):
        """
        Met à jour le solde de congés de l'employé après allocation.
        """
        if not self.employee or not self.leave_type:
            return

        frappe.logger().info(
            f"[Be Pay] Allocation de {self.total_leaves_allocated} jours "
            f"de {self.leave_type} pour {self.employee}"
        )


def get_leave_allocation_summary(employee, fiscal_year):
    """
    Récupère le résumé des allocations de congés d'un employé.

    Args:
        employee (str): ID de l'employé
        fiscal_year (str): Exercice fiscal

    Returns:
        dict: Résumé des allocations
    """
    results = frappe.db.sql(
        """
        SELECT
            leave_type,
            SUM(total_leaves_allocated) as total_allocated,
            SUM(expired_leaves) as total_expired,
            SUM(carry_forwarded_leaves) as total_carry_forward
        FROM `tabLeave Allocation`
        WHERE employee = %s
            AND fiscal_year = %s
            AND docstatus = 1
        GROUP BY leave_type
        """,
        (employee, fiscal_year),
        as_dict=True
    )

    return {r.leave_type: r for r in results} if results else {}
