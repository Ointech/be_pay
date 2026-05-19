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
        self._be_pay_auto_gift_salary()
        self._be_pay_validate_air_ticket()
        super().validate()

    def before_save(self):
        """
        Avant sauvegarde : mise à jour des champs calculés Be Pay.
        """
        self._be_pay_update_cost_center()
        self._be_pay_sync_category_salary()
        self._be_pay_track_salary_change()
        self._be_pay_update_family_details()

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
        if not self.employee_category_detail:
            return

        from be_pay.utils.payroll_utils import get_employee_category_salary

        salary_per_day = get_employee_category_salary(self.employee_category_detail)
        if salary_per_day is not None:
            self.pay_basic_salary_per_day = salary_per_day

    # ------------------------------------------------------------------
    # Suivi des changements de salaire (pay_salary_storie)
    # ------------------------------------------------------------------

    def _be_pay_track_salary_change(self):
        """
        Gère l'historique des changements de salaire dans la child table
        `pay_salary_storie`.

        Règles :
        - Premier enregistrement (nouvel employé ou salairy_old vide) :
          création d'une première ligne avec le CTC actuel.
        - Changement de CTC par rapport à salairy_old :
          fermeture de la dernière ligne (end_date = veille du nouveau
          start_date) puis création d'une nouvelle ligne.
        - Calcul du start_date selon Pay Payroll Settings :
          * Si use_payroll_period_by_employment_type est coché → day_start
            du type d'emploi pour le mois de la date de changement.
          * Sinon → 1er jour du mois de la date de changement.
        """
        ctc = frappe.utils.flt(self.ctc)

        if ctc <= 0:
            return

        # --- Premier enregistrement -------------------------------------
        if self.is_new() or not self.salairy_old:
            self._be_pay_add_salary_story()
            self.salairy_old = ctc
            return

        # --- Changement détecté -----------------------------------------
        if frappe.utils.flt(self.ctc) != frappe.utils.flt(self.salairy_old):
            self._be_pay_close_last_salary_story()
            self._be_pay_add_salary_story()
            self.salairy_old = self.ctc

    def _be_pay_add_salary_story(self):
        """Ajoute une nouvelle ligne dans `pay_salary_storie`."""
        start_date = self._be_pay_calculate_story_start_date()

        row = self.append("pay_salary_storie", {})
        row.ajust_date = frappe.utils.today()
        row.category = self.employee_category_detail
        row.salary = self.ctc
        row.start_date = start_date
        # end_date reste vide (période en cours)

    def _be_pay_close_last_salary_story(self):
        """
        Ferme la dernière ligne de `pay_salary_storie` en renseignant
        son end_date (veille du start_date de la nouvelle période).
        """
        if not self.pay_salary_storie:
            return

        last_row = self.pay_salary_storie[-1]
        new_start = self._be_pay_calculate_story_start_date()
        last_row.end_date = frappe.utils.add_days(new_start, -1)

    def _be_pay_calculate_story_start_date(self):
        """
        Calcule la date de début de la période selon la configuration
        Pay Payroll Settings.

        Returns:
            date: start_date à appliquer dans pay_salary_storie.
        """
        from frappe.utils import getdate, get_first_day, add_months, get_last_day
        from datetime import date

        today = getdate()
        settings = frappe.get_single("Pay Payroll Settings")

        # Mode configuré par type d'emploi
        if settings.use_payroll_period_by_employment_type:
            config = None
            for row in settings.payroll_period_details:
                if (
                    row.employment_type == self.employment_type
                    and row.company == self.company
                ):
                    config = row
                    break

            if config and config.day_start:
                day_start = int(config.day_start)
                try:
                    return date(today.year, today.month, day_start)
                except ValueError:
                    # jour trop grand pour ce mois (ex: 31 en février)
                    last_day = get_last_day(
                        date(today.year, today.month, 1)
                    ).day
                    return date(today.year, today.month, min(day_start, last_day))

        # Mode par défaut : 1er jour du mois courant
        return get_first_day(today)

    # ------------------------------------------------------------------
    # Gestion des détails familiaux (pay_family_details)
    # ------------------------------------------------------------------

    def _be_pay_update_family_details(self):
        """
        Calcule l'âge et le statut bénéficiaire pour chaque ligne de
        `pay_family_details`, puis retourne le nombre de lignes de type
        'Dependent' marquées comme bénéficiaires.

        Règles :
        - Dependent       → beneficiary = 1 (toujours)
        - Child / Others  → beneficiary = 1 si age < dependent_age
                            (paramètre de Pay Payroll Settings)
        """
        from frappe.utils import getdate, flt

        today = getdate()
        dependent_age_limit = flt(
            frappe.db.get_single_value("Pay Payroll Settings", "dependent_age") or 0
        )

        total_dependent_beneficiaries = 0

        count_child = 0
        count_dependent = 0

        for row in self.pay_family_details or []:
            # --- Calcul de l'âge ----------------------------------------
            if row.date_of_birth:
                dob = getdate(row.date_of_birth)
                age = (
                    today.year
                    - dob.year
                    - ((today.month, today.day) < (dob.month, dob.day))
                )
                row.age = age
            else:
                row.age = 0

            # --- Détermination du bénéficiaire --------------------------
            if row.type == "Dependent":
                row.beneficiary = 1
                count_dependent += 1
            elif row.type in ("Child", "Others"):
                if dependent_age_limit and row.age < dependent_age_limit:
                    row.beneficiary = 1
                    if row.type == "Child":
                        count_child += 1
                else:
                    row.beneficiary = 0
            else:
                row.beneficiary = 0

        # --- Mise à jour des compteurs sur Employee ------------------
        # child       = nombre de lignes Child bénéficiaires
        # dependent   = nombre total de lignes bénéficiaires (tous types)
        if hasattr(self, "child"):
            self.child = count_child
        if hasattr(self, "dependent"):
            self.dependent = count_child + count_dependent

        return count_child + count_dependent

    def _be_pay_auto_gift_salary(self):
        """
        Ajoute automatiquement une ligne 'Air Ticket' dans pay_gift_salary
        si l'Employment Type de l'employé a air_ticket = 1.
        """
        if not self.employment_type:
            return

        air_ticket = frappe.db.get_value(
            "Employment Type", self.employment_type, "air_ticket"
        )
        if not air_ticket:
            return

        # Vérifier si 'Air Ticket' existe déjà
        has_air_ticket = False
        for row in self.pay_gift_salary or []:
            if row.salary_component == "Air Ticket":
                has_air_ticket = True
                break

        if not has_air_ticket:
            row = self.append("pay_gift_salary", {})
            row.salary_component = "Air Ticket"
            row.type = "Earning"
            row.amount = 0

    def _be_pay_validate_air_ticket(self):
        """
        Valide que le composant 'Air Ticket' est présent dans pay_gift_salary
        si l'Employment Type de l'employé a air_ticket = 1.
        """
        if not self.employment_type:
            return

        air_ticket = frappe.db.get_value(
            "Employment Type", self.employment_type, "air_ticket"
        )
        if not air_ticket:
            return

        has_air_ticket = any(
            row.salary_component == "Air Ticket"
            for row in self.pay_gift_salary or []
        )

        if not has_air_ticket:
            frappe.throw(
                _(
                    "Le composant 'Air Ticket' est obligatoire dans la table Gift Salary "
                    "pour le type d'emploi {0}."
                ).format(self.employment_type)
            )


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


@frappe.whitelist()
def category_by():
    auto_assign = frappe.db.get_single_value(
        "Pay Payroll Settings",
        "auto_assign_employee_category_by_salary"
    )

    return {
        "auto_assign_employee_category_by_salary": auto_assign
    }


@frappe.whitelist()
def set_category_min_max(salary_ctc):
    salary_ctc = frappe.utils.flt(salary_ctc)

    working_day = frappe.db.get_single_value(
        "Pay Payroll Settings",
        "working_day"
    )

    working_day = frappe.utils.flt(working_day)

    if not working_day:
        frappe.throw("Please set Working Day in Pay Payroll Settings.")

    salary_by_day = salary_ctc / working_day

    data = frappe.db.sql("""
        SELECT name
        FROM `tabPay Employee Category Detail`
        WHERE %s BETWEEN min_salary AND max_salary
        LIMIT 1
    """, (salary_by_day,), as_dict=True)

    if data:
        return data[0]

    frappe.throw("No Employee Category found for this salary.")


@frappe.whitelist()
def set_category_salary(category):
    if not category:
        return {}

    data = frappe.db.get_value(
        "Pay Employee Category Detail",
        category,
        ["basic_salary"],
        as_dict=True
    )

    return data or {}


@frappe.whitelist()
def get_dependent_beneficiary_count(employee):
    """
    Retourne le nombre de lignes 'Dependent' marquées comme
    bénéficiaires pour un employé donné.

    Args:
        employee (str): ID de l'employé

    Returns:
        int: Nombre de Dependent bénéficiaires
    """
    if not employee:
        return 0

    doc = frappe.get_doc("Employee", employee)
    return doc._be_pay_update_family_details()