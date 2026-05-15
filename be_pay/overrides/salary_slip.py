# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Salary Slip pour Be Pay.

Intègre les heures de présence, les congés, les avances sur salaire
et les calculs d'ancienneté.
"""

import frappe
from frappe import _
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class CustomSalarySlip(SalarySlip):
    """
    Extension de la classe Salary Slip pour la logique Be Pay.
    """

    def before_insert(self):
        """
        Avant insertion : récupération des données de présence.
        """
        self._be_pay_fetch_attendance_data()
        super().before_insert()

    def before_save(self):
        """
        Avant sauvegarde : calcul des éléments de paie Be Pay.
        """
        self._be_pay_fetch_attendance_data()
        self._be_pay_fetch_mise_a_pied()
        self._be_pay_fetch_final_settlement()
        self._be_pay_fetch_leave_provision()
        self._be_pay_fetch_salary_advance()
        self._be_pay_fetch_bank_info()
        self._be_pay_calculate_anciennete()
        self._be_pay_update_leave_taken()
        super().before_save()

    def before_validate(self):
        """
        Avant validation : synchronisation de l'ancienneté.
        """
        self._be_pay_calculate_anciennete()
        super().before_validate()

    def before_submit(self):
        """
        Avant soumission : assignation du salaire catégorisé.
        """
        self._be_pay_assign_category_salary()
        super().before_submit()

    def after_insert(self):
        """
        Après insertion : assignation initiale du salaire.
        """
        self._be_pay_assign_category_salary()
        super().after_insert()

    def _be_pay_fetch_attendance_data(self):
        """
        Récupère les données de présence depuis Attendance Line.
        """
        if not self.pay_period or not self.employee:
            return

        from be_pay.utils.payroll_utils import get_attendance_summary

        summary = get_attendance_summary(self.pay_period, self.employee)
        if not summary:
            return

        self.custom_heure_suplementaire = summary.get("sunday_hours", 0)
        self.custom_absences = summary.get("absence", 0)
        self.custom_jours_mise_a_pied = summary.get("custom_mise_a_pied", 0)
        self.custom_presence = summary.get("custom_presence", 0)
        self.custom_h30 = summary.get("hours_30", 0)
        self.custom_h60 = summary.get("hours_60", 0)
        self.custom_h100 = summary.get("sunday_hours", 0)
        self.custom_abscences = summary.get("absence", 0)
        self.custom_sm = summary.get("custom_sm", 0)

        # Calcul des heures de nuit
        night_hours = (
            (summary.get("a1") or 0) * 1 +
            (summary.get("a2") or 0) * 2 +
            (summary.get("a3") or 0) * 2 +
            (summary.get("a4") or 0) * 3 +
            (summary.get("a5") or 0) * 3.3 +
            (summary.get("a6") or 0) * 4 +
            (summary.get("a7") or 0) * 5 +
            (summary.get("a8") or 0) * 6 +
            (summary.get("a9") or 0) * 10 +
            (summary.get("n1") or 0) * 7 +
            (summary.get("n2") or 0) * 6.3 +
            (summary.get("n3") or 0) * 7
        )
        self.night_hours = night_hours

    def _be_pay_fetch_mise_a_pied(self):
        """
        Récupère les jours de mise à pied depuis Leave Application.
        """
        if not self.employee or not self.start_date or not self.end_date:
            return

        results = frappe.db.sql(
            """
            SELECT
                SUM(
                    DATEDIFF(
                        LEAST(s.to_date, %(end_date)s),
                        GREATEST(s.from_date, %(start_date)s)
                    ) + 1
                ) AS total_days
            FROM `tabLeave Application` s
            WHERE s.employee = %(employee)s
                AND s.docstatus = 1
                AND s.from_date <= %(end_date)s
                AND s.to_date >= %(start_date)s
                AND s.leave_type = %(leave_type)s
            """,
            {
                "employee": self.employee,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "leave_type": "Mise à pied"
            },
            as_dict=True
        )

        if results and results[0].total_days:
            self.custom_jours_mise_a_pied = results[0].total_days
        else:
            self.custom_jours_mise_a_pied = 0

    def _be_pay_fetch_final_settlement(self):
        """
        Récupère les données du décompte final si applicable.
        """
        if not self.employee or not self.start_date or not self.end_date:
            return

        decompte_list = frappe.db.sql(
            """
            SELECT *
            FROM `tabFinal Settlement`
            WHERE employee = %s
                AND date_fin_contrat BETWEEN %s AND %s
                AND docstatus = 1
            """,
            (self.employee, self.start_date, self.end_date),
            as_dict=True
        )

        if decompte_list:
            self.custom_total_days = decompte_list[0].total_jours
            self.custom_jour_preste = decompte_list[0].jour_preste
        else:
            self.custom_total_days = 0
            self.custom_jour_preste = 0

    def _be_pay_fetch_leave_provision(self):
        """
        Récupère les données de provision de congés.
        """
        if not self.employee or not self.end_date:
            return

        projet_val = frappe.utils.getdate(self.end_date).year

        periods = frappe.get_all(
            "Pay Provision",
            filters={
                "fiscal_year": projet_val,
                "employment_type": self.employment_type
            },
            fields=["name", "start_date", "end_date"],
            limit=1
        )

        if not periods:
            return

        self.from_date = periods[0].start_date
        self.to_date = periods[0].end_date

        conge_list = frappe.db.sql(
            """
            SELECT *
            FROM `tabProvision Ratio`
            WHERE employee = %s AND parent = %s
            """,
            (self.employee, periods[0].name),
            as_dict=True
        )

        if conge_list:
            self.leave_allouer = (
                int(conge_list[0].pris or 0) +
                int(conge_list[0].total or 0) -
                int(conge_list[0].report or 0)
            )
            self.pris = conge_list[0].pris
            self.reste_a_prendre = conge_list[0].total
            self.custom_repport = conge_list[0].report

    def _be_pay_fetch_salary_advance(self):
        """
        Récupère l'avance sur salaire de la période.
        """
        if not self.employee or not self.start_date or not self.end_date:
            return

        result = frappe.db.sql(
            """
            SELECT MAX(incentive_amount) AS amount
            FROM `tabEmployee Incentive`
            WHERE docstatus = 1
                AND salary_component = 'Salary Advance'
                AND employee = %s
                AND payroll_date BETWEEN %s AND %s
            """,
            (self.employee, self.start_date, self.end_date)
        )

        if result and result[0][0]:
            self.custom_total_avance = result[0][0]

    def _be_pay_fetch_bank_info(self):
        """
        Récupère et calcule la répartition bancaire/cash/autres.
        """
        if not self.employee:
            return

        emp = frappe.db.get_value(
            "Employee",
            self.employee,
            "local_bank",
            as_dict=True
        )

        if emp and not self.custom_get_local_bank:
            self.bank = emp.local_bank

        if self.net_pay:
            self.autres = float(self.net_pay)
            if self.cash is not None and self.bank is not None:
                self.autres = float(self.net_pay) - float(self.cash) - float(self.bank)
            elif self.cash is not None:
                self.autres = float(self.net_pay) - float(self.cash)
            elif self.bank is not None and self.bank != 0:
                self.autres = 0
            else:
                self.autres = float(self.net_pay)

    def _be_pay_calculate_anciennete(self):
        """
        Calcule et synchronise l'ancienneté depuis l'employé.
        """
        if not self.employee:
            return

        employee_doc = frappe.get_doc("Employee", self.employee)

        from be_pay.utils.payroll_utils import calculate_anciennete

        anciennete = calculate_anciennete(employee_doc.date_of_joining)
        self.anciennete = anciennete
        employee_doc.anciennete = anciennete

        # Ancienneté fin de prestation
        if employee_doc.scheduled_confirmation_date:
            anciennete_fin = calculate_anciennete(
                employee_doc.scheduled_confirmation_date
            )
            self.custom_anciennete_fin_prestation = anciennete_fin
            employee_doc.custom_ancienneté_fin_préstation = anciennete_fin

        employee_doc.save()

    def _be_pay_update_leave_taken(self):
        """
        Met à jour la table Salary Slip Taken avec les congés pris.
        """
        if not self.employee or not self.start_date or not self.end_date:
            return

        from be_pay.utils.payroll_utils import get_leave_taken

        leaves = get_leave_taken(self.employee, self.start_date, self.end_date)

        if not leaves:
            return

        for leave in leaves:
            total_days = leave.total_leave_days
            if total_days > 26:
                total_days = 26

            existing = frappe.db.sql(
                """
                SELECT name
                FROM `tabSalary Slip Taken`
                WHERE parent = %s AND leave_type = %s
                LIMIT 1
                """,
                (self.name, leave.leave_type)
            )

            if not existing:
                self.append("leave_taken", {
                    "leave_type": leave.leave_type,
                    "total_leave_days": total_days
                })

    def _be_pay_assign_category_salary(self):
        """
        Assigne le salaire catégorisé au départ ou en normal.
        """
        if not self.employee:
            return

        employee_doc = frappe.get_doc("Employee", self.employee)

        salary = employee_doc.pay_basic_salary_per_day or 0
        self.custom_salaire_categorise_au_depart = salary
        self.basic_salary_per_day = salary

    def _be_pay_calculate_anciennete_day(self):
        """
        Calcule l'ancienneté en années avec décimale (basé sur les mois).
        """
        if not self.date_embauche or not self.to_date:
            return

        from be_pay.utils.payroll_utils import calculate_months_between

        months = calculate_months_between(self.date_embauche, self.to_date)
        self.anciennete_day = months / 12


def get_salary_slip_totals(employee, fiscal_year):
    """
    Récupère les totaux des fiches de paie d'un employé pour un exercice fiscal.

    Args:
        employee (str): ID de l'employé
        fiscal_year (str): Exercice fiscal

    Returns:
        dict: Totaux des fiches de paie
    """
    results = frappe.db.sql(
        """
        SELECT
            COUNT(*) as count,
            SUM(net_pay) as total_net_pay,
            SUM(gross_pay) as total_gross_pay
        FROM `tabSalary Slip`
        WHERE employee = %s
            AND fiscal_year = %s
            AND docstatus = 1
        """,
        (employee, fiscal_year),
        as_dict=True
    )

    return results[0] if results else {}
