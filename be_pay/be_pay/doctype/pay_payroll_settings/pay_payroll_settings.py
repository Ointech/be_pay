import frappe
from frappe import _
from frappe.model.document import Document


class PayPayrollSettings(Document):
    def validate(self):
        """
        Valide que les tables enfants ne contiennent pas de doublons.
        """
        self._validate_no_duplicate_salary_components()
        self._validate_no_duplicate_payroll_period_details()

    def _validate_no_duplicate_salary_components(self):
        """
        Vérifie qu'un même Salary Component n'apparaît pas deux fois
        dans la table attendance_salary_components.
        """
        seen = set()
        for row in self.attendance_salary_components or []:
            if row.salary_component in seen:
                frappe.throw(
                    _(
                        "Le Salary Component '{0}' est déjà présent dans la table "
                        "Attendance Salary Components. Les doublons ne sont pas autorisés."
                    ).format(row.salary_component)
                )
            seen.add(row.salary_component)

    def _validate_no_duplicate_payroll_period_details(self):
        """
        Vérifie qu'un même couple (Employment Type, Company) n'apparaît pas deux fois
        dans la table payroll_period_details.
        """
        seen = set()
        for row in self.payroll_period_details or []:
            key = (row.employment_type, row.company)
            if key in seen:
                frappe.throw(
                    _(
                        "La combinaison Employment Type '{0}' + Company '{1}' est déjà "
                        "présente dans la table Payroll Period Details. Les doublons ne sont pas autorisés."
                    ).format(row.employment_type, row.company)
                )
            seen.add(key)
