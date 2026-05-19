# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt, get_last_day, add_months, add_days

MONTH_FIELDS = [
    "pay_january", "pay_february", "pay_march", "pay_april",
    "pay_may", "pay_june", "pay_july", "pay_august",
    "pay_september", "pay_october", "pay_november", "pay_december"
]

MONTH_LABELS = [
    "janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre"
]

MONTH_INDEX_MAP = {
    "January": 0, "February": 1, "March": 2, "April": 3,
    "May": 4, "June": 5, "July": 6, "August": 7,
    "September": 8, "October": 9, "November": 10, "December": 11
}

TABLE_FIELD_TO_DOCTYPE = {
    "pay_ratio": "Pay Provision Ratio",
    "pay_leave": "Pay Provision Leave",
    "pay_gratuity_amount": "Pay Provision Gratuity",
    "pay_bonus_amount": "Pay Provision Bonus",
    "pay_ticket": "Pay Provision Ticket",
}


class PayProvision(Document):
    def autoname(self):
        if self.employment_type:
            self.name = f"{self.fiscal_year}PROV{self.employment_type}"
        else:
            self.name = f"{self.fiscal_year}PROV-GLOBAL"

    def before_save(self):
        self.calculate_provisions()
        self._validate_bonus_provision()

    def on_submit(self):
        """Crée les Leave Allocations à partir des ratios calculés."""
        for row in self.pay_ratio:
            if not row.employee:
                continue

            doc = frappe.new_doc("Leave Allocation")
            doc.leave_type = self.leave_type
            doc.employee = row.employee
            doc.new_leaves_allocated = row.pay_total
            doc.from_date = self.start_date
            doc.to_date = self.end_date
            doc.submit()

            # total_leaves_allocated doit correspondre exactement au pay_total
            if flt(doc.total_leaves_allocated) != flt(row.pay_total):
                frappe.db.set_value(
                    "Leave Allocation",
                    doc.name,
                    {
                        "total_leaves_allocated": row.pay_total,
                        "unused_leaves": row.pay_report,
                    },
                    update_modified=False,
                )

    def before_cancel(self):
        self._validate_cancel_sequence()

    def on_cancel(self):
        self._cancel_linked_leave_allocations()

    def _validate_cancel_sequence(self):
        """
        On ne peut annuler une provision que si aucune provision plus récente
        n'existe pour la même company / leave_type (et employment_type compatible).
        """
        filters = {
            "company": self.company,
            "leave_type": self.leave_type,
            "docstatus": 1,
            "end_date": (">", self.end_date),
            "name": ("!=", self.name),
        }
        newer_provisions = frappe.get_all(
            "Pay Provision", filters=filters, fields=["name", "employment_type"]
        )
        for prov in newer_provisions:
            if (
                not self.employment_type
                or not prov.employment_type
                or self.employment_type == prov.employment_type
            ):
                frappe.throw(
                    _(
                        "Vous ne pouvez pas annuler cette provision car la provision {0} "
                        "(année ultérieure) existe. Veuillez l'annuler d'abord."
                    ).format(prov.name)
                )

    def _cancel_linked_leave_allocations(self):
        """
        Si Pay Payroll Settings > revoke_allowance_on_provision_cancellation est coché,
        annule les Leave Allocation liées, sauf si des Leave Application existent.
        """
        revoke = cint(
            frappe.db.get_single_value(
                "Pay Payroll Settings", "revoke_allowance_on_provision_cancellation"
            )
        )
        if not revoke:
            return

        for row in self.pay_ratio:
            if not row.employee:
                continue

            has_leaves = frappe.db.exists(
                "Leave Application",
                {
                    "employee": row.employee,
                    "leave_type": self.leave_type,
                    "docstatus": 1,
                    "from_date": ("<=", self.end_date),
                    "to_date": (">=", self.start_date),
                },
            )
            if has_leaves:
                frappe.throw(
                    _(
                        "Impossible d'annuler la provision : des demandes de congé "
                        "(Leave Application) existent pour l'employé {0} sur cette période."
                    ).format(row.employee)
                )

            allocations = frappe.get_all(
                "Leave Allocation",
                filters={
                    "employee": row.employee,
                    "leave_type": self.leave_type,
                    "from_date": self.start_date,
                    "to_date": self.end_date,
                    "docstatus": 1,
                },
                pluck="name",
            )
            for alloc_name in allocations:
                alloc = frappe.get_doc("Leave Allocation", alloc_name)
                alloc.cancel()

    # ------------------------------------------------------------------
    # Validation Pay Bonus Provision
    # ------------------------------------------------------------------

    def _validate_bonus_provision(self):
        """
        Si le type d'emploi a have_bonus=1,
        on vérifie qu'un Pay Bonus Provision existe pour cette année fiscale.
        En mode global, on vérifie pour tous les types présents.
        """
        if not self.fiscal_year:
            return

        settings = frappe.get_single("Pay Settings Leave Accrual")
        if settings.apply_accrual_to_all_employment_types:
            # Mode global : vérifier s'il existe au moins un employé avec have_bonus
            # et si le Pay Bonus Provision existe
            emp_filters = {"status": "Active"}
            if self.company:
                emp_filters["company"] = self.company
            emp_types = frappe.get_all(
                "Employee", filters=emp_filters, pluck="employment_type", distinct=1
            )
            has_any_bonus = any(
                cint(frappe.db.get_value("Employment Type", et, "have_bonus"))
                for et in emp_types if et
            )
            if not has_any_bonus:
                return
        else:
            if not self.employment_type:
                return
            has_any_bonus = cint(
                frappe.db.get_value("Employment Type", self.employment_type, "have_bonus")
            )
            if not has_any_bonus:
                return

        exists = frappe.db.exists(
            "Pay Bonus Provision",
            {"fiscal_year": self.fiscal_year, "docstatus": ("<", 2)}
        )
        if not exists:
            frappe.throw(
                _(
                    "Veuillez créer les pourcentages Pay Bonus Provision pour l'année fiscale {0}"
                ).format(self.fiscal_year)
            )

    # ------------------------------------------------------------------
    # Calcul principal des provisions
    # ------------------------------------------------------------------

    def calculate_provisions(self):
        """
        Calcule et remplit les 5 child tables de provision :
        pay_ratio, pay_leave, pay_gratuity_amount, pay_bonus_amount, pay_ticket.
        """
        if not self.start_date or not self.end_date:
            return

        settings = frappe.get_single("Pay Settings Leave Accrual")
        is_global = settings.apply_accrual_to_all_employment_types

        if not is_global and not self.employment_type:
            return

        # Sauvegarder pay_taken existant avant de vider
        preserved = {}
        for field in [
            "pay_ratio",
            "pay_leave",
            "pay_gratuity_amount",
            "pay_ticket",
            "pay_bonus_amount",
        ]:
            preserved[field] = {
                row.employee: flt(row.pay_taken)
                for row in (getattr(self, field) or [])
                if getattr(row, "employee", None)
            }

        # Vider les anciennes lignes
        for field in [
            "pay_ratio",
            "pay_leave",
            "pay_gratuity_amount",
            "pay_ticket",
            "pay_bonus_amount",
        ]:
            setattr(self, field, [])

        # Paramètres globaux
        working_day = flt(
            frappe.db.get_single_value("Pay Payroll Settings", "working_day") or 26
        )

        # Récupérer la configuration d'accroche
        accrual_config = self._get_accrual_config()
        if not accrual_config:
            frappe.throw(
                _(
                    "Veuillez configurer les ratios d'accroche dans Pay Settings Leave Accrual"
                )
            )

        monthly_ratio = accrual_config.get("monthly_leave_accrual_days", 0)

        # Récupérer les employés
        emp_filters = {"status": "Active"}
        if self.company:
            emp_filters["company"] = self.company
        if not is_global:
            emp_filters["employment_type"] = self.employment_type

        employees = frappe.get_all(
            "Employee",
            filters=emp_filters,
            fields=[
                "name",
                "employment_type",
                "date_of_joining",
                "relieving_date",
                "ctc",
                "housing",
                "transport",
                "allowance",
            ],
        )

        for emp in employees:
            emp_bonus = cint(
                frappe.db.get_value("Employment Type", emp.employment_type, "have_bonus")
            )
            emp_ticket = cint(
                frappe.db.get_value("Employment Type", emp.employment_type, "air_ticket")
            )
            self._calculate_employee_provisions(
                emp, monthly_ratio, working_day, emp_bonus, emp_ticket, preserved
            )

    def _get_accrual_config(self):
        """
        Retourne la configuration d'accroche.
        En mode global, retourne le ratio global.
        En mode par type, retourne le ratio spécifique au type du document.
        """
        settings = frappe.get_single("Pay Settings Leave Accrual")

        if settings.apply_accrual_to_all_employment_types:
            return {
                "monthly_leave_accrual_days": flt(settings.monthly_leave_accrual_days),
            }

        if not self.employment_type:
            return None

        for row in settings.leave_accrual_detail or []:
            if row.employment_type == self.employment_type:
                return {
                    "monthly_leave_accrual_days": flt(row.leave_accrual),
                }

        return None

    def _get_seniority_bonus(self, years_of_service, employment_type):
        """
        Retourne le nombre de jours bonus d'ancienneté depuis Pay Leave Seniority Bonus.
        Prend la ligne avec le plus grand segnority <= years_of_service.
        """
        if not employment_type:
            return 0

        company = self.company
        if not company:
            return 0

        config = frappe.get_all(
            "Pay Leave Seniority Bonus",
            filters={"company": company},
            fields=["name", "use_for_type_of_employee"],
            limit=1,
        )
        if not config:
            return 0

        config = config[0]
        detail_filters = {"parent": config.name}
        if cint(config.use_for_type_of_employee):
            detail_filters["employment_type"] = employment_type

        rows = frappe.get_all(
            "Pay Leave Seniority Bonus Detail",
            filters=detail_filters,
            fields=["segnority", "day_number"],
            order_by="segnority DESC",
        )

        for row in rows:
            if flt(row.segnority) <= flt(years_of_service):
                return flt(row.day_number)

        return 0

    def _calculate_employee_provisions(
        self, emp, monthly_ratio, working_day, type_have_bonus, type_have_ticket, preserved
    ):
        """
        Calcule les 12 mois de provisions pour un employé donné.
        """
        # --- Données annexes ---
        stories = frappe.get_all(
            "Pay Salary Storie",
            filters={
                "parent": emp.name,
                "parenttype": "Employee",
                "parentfield": "pay_salary_storie",
            },
            fields=["salary", "start_date", "end_date"],
            order_by="start_date",
        )

        gifts = frappe.get_all(
            "Pay Gift Salary",
            filters={
                "parent": emp.name,
                "parenttype": "Employee",
                "parentfield": "pay_gift_salary",
            },
            fields=["amount", "type", "salary_component"],
        )

        air_ticket_amount = sum(
            flt(g.amount) for g in gifts if g.salary_component == "Air Ticket"
        )

        gift_earnings = sum(
            flt(g.amount)
            for g in gifts
            if g.type == "Earning" and g.salary_component != "Air Ticket"
        )
        gift_deductions = sum(flt(g.amount) for g in gifts if g.type == "Deduction")
        gift_net = gift_earnings - gift_deductions

        fixed_allowances = flt(emp.housing) + flt(emp.transport) + flt(emp.allowance)

        # --- Calcul mensuel (1ère passe : ratios) ---
        ratios = []
        conges = []
        bonuses = []
        tickets = []
        salaries = []

        base_start = getdate(self.start_date)
        base_end = getdate(self.end_date)
        fiscal_year_start = base_start

        # Années de service jusqu'à la fin de la période (avec décimales comme Excel)
        years_of_service = self._get_years_of_service_months(
            getdate(emp.date_of_joining), base_end
        )
        bonus_days = self._get_seniority_bonus(years_of_service, emp.employment_type)

        # Récupération des cumuls externes si initialisation report
        selected_month_idx = None
        cumul_ratio = 0.0
        cumul_leave = 0.0

        if self.is_external_report and self.external_report_month:
            selected_month_idx = MONTH_INDEX_MAP.get(self.external_report_month)
            if selected_month_idx is not None:
                cumul_doc = frappe.get_all(
                    "Pay Provision Cumul",
                    filters={
                        "employee": emp.name,
                        "company": self.company,
                        "fiscal_year": self.fiscal_year,
                    },
                    fields=["value_ratio_report", "value_leave_report"],
                    limit=1,
                )
                if cumul_doc:
                    cumul_ratio = flt(cumul_doc[0].value_ratio_report)
                    cumul_leave = flt(cumul_doc[0].value_leave_report)
                    if not cumul_leave and cumul_ratio and working_day:
                        base_salary = flt(emp.ctc) or 0
                        if base_salary:
                            cumul_leave = cumul_ratio * base_salary / working_day

        # Pourcentages bonus depuis Pay Bonus Provision
        bonus_percentages = {}
        if type_have_bonus and self.fiscal_year:
            bonus_prov = frappe.get_all(
                "Pay Bonus Provision",
                filters={"fiscal_year": self.fiscal_year, "docstatus": 1},
                fields=["name"],
                limit=1,
            )
            if bonus_prov:
                for d in frappe.get_all(
                    "Pay Provision Gratuity Detail",
                    filters={"parent": bonus_prov[0].name},
                    fields=["employee", "pay_percentage"],
                ):
                    bonus_percentages[d.employee] = flt(d.pay_percentage)

        for month in range(1, 13):
            period_start = add_months(base_start, month - 1)
            period_end = add_days(add_months(base_start, month), -1)
            if period_end > base_end:
                period_end = base_end

            # Vérifier activité (implicite dans Excel mais nécessaire en dynamique)
            active_start, active_end = self._get_active_period(
                emp.date_of_joining, emp.relieving_date, period_start, period_end
            )
            if active_start > period_end or active_end < period_start:
                ratios.append(0.0)
                conges.append(0.0)
                bonuses.append(0.0)
                tickets.append(0.0)
                salaries.append(0.0)
                continue

            # Si initialisation externe : mois avant le mois sélectionné = 0
            if selected_month_idx is not None and (month - 1) < selected_month_idx:
                ratios.append(0.0)
                conges.append(0.0)
                bonuses.append(0.0)
                tickets.append(0.0)
                salaries.append(0.0)
                continue

            # Si initialisation externe : mois sélectionné = cumul externe
            if selected_month_idx is not None and (month - 1) == selected_month_idx:
                ratios.append(cumul_ratio)
                salary = self._get_applicable_salary(
                    emp, stories, period_start, period_end
                )
                salary += fixed_allowances + gift_net
                salaries.append(salary)
                if cumul_leave:
                    conges.append(cumul_leave)
                elif cumul_ratio and working_day:
                    conges.append(salary / working_day * cumul_ratio)
                else:
                    conges.append(0.0)
                emp_pct = bonus_percentages.get(emp.name)
                if emp_pct:
                    bonuses.append(salary * emp_pct / 100 / 12)
                else:
                    bonuses.append(0.0)
                if type_have_ticket:
                    tickets.append(flt(air_ticket_amount) / 12)
                else:
                    tickets.append(0.0)
                continue

            # Calcul normal
            ratio = self._get_monthly_ratio(
                emp, monthly_ratio, period_start, fiscal_year_start, bonus_days
            )

            ratios.append(ratio)

            # Salaire applicable pour cette période
            salary = self._get_applicable_salary(
                emp, stories, period_start, period_end
            )
            salary += fixed_allowances + gift_net
            salaries.append(salary)

            # Congé ($) = salaire / working_day * ratio
            conges.append(salary / working_day * ratio)

            # Bonus (si have_bonus = 1 et employé listé dans Pay Bonus Provision)
            if type_have_bonus:
                emp_pct = bonus_percentages.get(emp.name)
                if emp_pct:
                    bonuses.append(salary * emp_pct / 100 / 12)
                else:
                    bonuses.append(0.0)
            else:
                bonuses.append(0.0)

            # Ticket (si air_ticket = 1 pour ce type)
            if type_have_ticket:
                tickets.append(flt(air_ticket_amount) / 12)
            else:
                tickets.append(0.0)

        # --- 2ème passe : gratification ---
        ratio_total = sum(ratios)
        gratifs = []
        for i in range(12):
            if ratio_total > 0 and salaries[i]:
                gratifs.append(salaries[i] / ratio_total * ratios[i])
            else:
                gratifs.append(0.0)

        # --- Création des lignes dans les child tables ---
        self._add_provision_row("pay_ratio", emp.name, ratios, preserved.get("pay_ratio", {}))
        self._add_provision_row("pay_leave", emp.name, conges, preserved.get("pay_leave", {}))
        self._add_provision_row("pay_gratuity_amount", emp.name, gratifs, preserved.get("pay_gratuity_amount", {}))
        if type_have_bonus:
            self._add_provision_row("pay_bonus_amount", emp.name, bonuses, preserved.get("pay_bonus_amount", {}))
        if type_have_ticket:
            self._add_provision_row("pay_ticket", emp.name, tickets, preserved.get("pay_ticket", {}))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_monthly_ratio(self, emp, monthly_base, period_start, fiscal_year_start, bonus_days):
        """
        Calcule le ratio mensuel selon les formules Excel exactes.
        Base de prorata : 30 jours.
        """
        join_date = getdate(emp.date_of_joining) if emp.date_of_joining else getdate("1900-01-01")
        relieving = getdate(emp.relieving_date) if emp.relieving_date else None
        current_year_start = max(join_date, fiscal_year_start)
        days_in_month = get_last_day(period_start).day

        # Prorata sortie
        if relieving and relieving < period_start:
            return 0.0
        if relieving and relieving.month == period_start.month and relieving.year == period_start.year:
            ratio = monthly_base / 30.0 * (relieving - period_start).days
        # Prorata entrée dans l'année courante
        elif current_year_start > period_start and current_year_start.month == period_start.month:
            ratio = monthly_base / 30.0 * (days_in_month - current_year_start.day)
        # Mois normal
        else:
            ratio = monthly_base

        # Bonus au mois anniversaire
        if join_date.month == period_start.month and ratio > 0:
            ratio += bonus_days

        return flt(ratio, 2)

    def _get_active_period(self, date_join, date_quit, period_start, period_end):
        """
        Retourne la portion active de la période compte tenu de l'embauche
        et du départ de l'employé.
        """
        join_date = getdate(date_join) if date_join else getdate("1900-01-01")
        quit_date = getdate(date_quit) if date_quit else None

        active_start = max(join_date, period_start)
        active_end = min(quit_date or period_end, period_end)
        return active_start, active_end

    def _get_years_of_service(self, date_join, as_of_date):
        """Calcule les années de service complètes."""
        if not date_join or not as_of_date:
            return 0
        years = as_of_date.year - date_join.year
        if (as_of_date.month, as_of_date.day) < (date_join.month, date_join.day):
            years -= 1
        return max(0, years)

    def _get_years_of_service_months(self, date_join, as_of_date):
        """Calcule les années de service avec décimales (comme DATEDIF(...,"m")/12)."""
        if not date_join or not as_of_date:
            return 0
        months = (as_of_date.year - date_join.year) * 12 + (as_of_date.month - date_join.month)
        if as_of_date.day < date_join.day:
            months -= 1
        return max(0, months) / 12.0

    def _get_applicable_salary(self, emp, stories, period_start, period_end):
        """
        Retourne le salaire applicable pour la période depuis pay_salary_storie.
        Si aucune ligne ne correspond, retourne le CTC actuel de l'employé.
        """
        if not stories:
            return flt(emp.ctc)

        for story in stories:
            story_start = getdate(story.start_date) if story.start_date else getdate(
                "1900-01-01"
            )
            story_end = (
                getdate(story.end_date)
                if story.end_date
                else getdate("2099-12-31")
            )

            if story_start <= period_end and story_end >= period_start:
                return flt(story.salary)

        return flt(emp.ctc)

    def _get_last_provision_report(self, employee, table_field):
        """
        Retourne le pay_total de la dernière provision soumise pour cet employé
        dans la même table enfant (company, leave_type, date antérieure).
        """
        child_doctype = TABLE_FIELD_TO_DOCTYPE.get(table_field)
        if not child_doctype:
            return 0.0

        result = frappe.db.sql(
            """
            SELECT r.pay_total
            FROM `tabPay Provision` p
            INNER JOIN `tab{child_doctype}` r ON p.name = r.parent
            WHERE r.employee = %s
              AND p.company = %s
              AND p.leave_type = %s
              AND p.docstatus = 1
              AND p.end_date < %s
            ORDER BY p.end_date DESC
            LIMIT 1
            """.format(child_doctype=child_doctype),
            (employee, self.company, self.leave_type, self.start_date),
        )
        return flt(result[0][0]) if result else 0.0

    def _add_provision_row(self, table_field, employee, monthly_values, preserved_taken):
        """Ajoute une ligne dans la child table de provision indiquée."""
        total = sum(monthly_values)
        report = flt(self._get_last_provision_report(employee, table_field), 2)

        if total == 0 and report == 0:
            return

        row = self.append(table_field, {})
        row.employee = employee
        row.employee_name = frappe.db.get_value("Employee", employee, "employee_name") or ""
        row.pay_report = report

        for i, val in enumerate(monthly_values):
            setattr(row, MONTH_FIELDS[i], flt(val, 2))

        row.pay_taken = flt(preserved_taken.get(employee, 0), 2)
        row.pay_total = flt(total + report, 2)


# ------------------------------------------------------------------------------
# Méthodes whitelisted
# ------------------------------------------------------------------------------

@frappe.whitelist()
def update_pay_provision(name):
    """
    Recalcule les lignes de provision pour un document Pay Provision existant.
    Appelé depuis le bouton 'Mettre à jour' du formulaire.
    """
    doc = frappe.get_doc("Pay Provision", name)
    doc.calculate_provisions()
    doc.save()
    return {"status": "ok"}


@frappe.whitelist()
def update_provision_for_employee(fiscal_year, leave_type, emp_name):
    """
    Met à jour les provisions d'un employé donné pour une année fiscale.
    Trouve le Pay Provision correspondant et le recalcule entièrement.
    """
    emp = frappe.get_doc("Employee", emp_name)
    if not emp or not emp.employment_type:
        frappe.throw(_("Employé ou type d'emploi non trouvé"))

    provisions = frappe.get_all(
        "Pay Provision",
        filters={
            "fiscal_year": fiscal_year,
            "employment_type": emp.employment_type,
            "leave_type": leave_type,
            "docstatus": 0,
        },
        pluck="name",
    )

    if not provisions:
        # Chercher une provision globale
        provisions = frappe.get_all(
            "Pay Provision",
            filters={
                "fiscal_year": fiscal_year,
                "employment_type": ("is", "not set"),
                "leave_type": leave_type,
                "docstatus": 0,
            },
            pluck="name",
        )

    if not provisions:
        frappe.throw(
            _(
                "Aucune provision trouvée pour l'année fiscale {0}, le type de congé {1} et le type d'emploi {2}"
            ).format(fiscal_year, leave_type, emp.employment_type)
        )

    doc = frappe.get_doc("Pay Provision", provisions[0])
    doc.calculate_provisions()
    doc.save()
    return {"status": "ok", "provision": doc.name}


@frappe.whitelist()
def init_provision_for_employee(fiscal_year, emp_name):
    """
    Crée ou recalcule la provision d'un employé pour une année fiscale.
    Si aucune provision n'existe, tente de la créer automatiquement.
    """
    emp = frappe.get_doc("Employee", emp_name)
    if not emp or not emp.employment_type:
        frappe.throw(_("Employé ou type d'emploi non trouvé"))

    # Chercher une provision existante (par type ou globale)
    provisions = frappe.get_all(
        "Pay Provision",
        filters={
            "fiscal_year": fiscal_year,
            "employment_type": emp.employment_type,
            "docstatus": 0,
        },
        pluck="name",
    )

    if not provisions:
        provisions = frappe.get_all(
            "Pay Provision",
            filters={
                "fiscal_year": fiscal_year,
                "employment_type": ("is", "not set"),
                "docstatus": 0,
            },
            pluck="name",
        )

    if provisions:
        doc = frappe.get_doc("Pay Provision", provisions[0])
    else:
        # Créer automatiquement
        fy = frappe.get_doc("Fiscal Year", fiscal_year)
        doc = frappe.new_doc("Pay Provision")
        doc.fiscal_year = fiscal_year
        doc.employment_type = emp.employment_type
        doc.start_date = fy.year_start_date
        doc.end_date = fy.year_end_date
        doc.insert()

    doc.calculate_provisions()
    doc.save()
    return {"status": "ok", "provision": doc.name}


@frappe.whitelist()
def get_dates_by_employment_type(employment_type=None, company=None, fiscal_year=None):
    """
    Calcule start_date et end_date pour Payroll Entry selon la configuration Be Pay.
    """
    from dateutil.relativedelta import relativedelta

    if not fiscal_year:
        frappe.throw(_("Fiscal Year is required"))

    settings = frappe.get_single("Pay Payroll Settings")
    use_be_pay = settings.use_payroll_period_by_employment_type

    if not use_be_pay:
        pp = frappe.db.get_value(
            "Fiscal Year",
            fiscal_year,
            ["year_start_date", "year_end_date"],
            as_dict=True
        )
        if not pp:
            frappe.throw(_("Fiscal Year not found"))
        return {
            "start_date": str(pp.year_start_date),
            "end_date": str(pp.year_end_date)
        }

    if not employment_type:
        pp = frappe.db.get_value(
            "Fiscal Year",
            fiscal_year,
            ["year_start_date", "year_end_date"],
            as_dict=True
        )
        if not pp:
            frappe.throw(_("Fiscal Year not found"))
        return {
            "start_date": str(pp.year_start_date),
            "end_date": str(pp.year_end_date)
        }

    config = None
    for row in settings.payroll_period_details:
        if row.employment_type == employment_type and row.company == company:
            config = row
            break

    if not config:
        frappe.throw(
            _("No Fiscal Year configuration found for Employment Type: {0} and Company: {1}").format(
                employment_type, company
            )
        )

    pp = frappe.db.get_value(
        "Fiscal Year",
        fiscal_year,
        ["year_start_date", "year_end_date"],
        as_dict=True
    )
    if not pp:
        frappe.throw(_("Fiscal Year not found"))

    base = getdate(pp.year_start_date)
    year = base.year
    month = base.month
    day_start = cint(config.day_start or 1)
    day_end = cint(config.day_end or 31)

    if day_start <= day_end:
        start_date = _safe_date(year, month, day_start)
    else:
        start_month = month - 1 if month > 1 else 12
        start_year = year if month > 1 else year - 1
        start_date = _safe_date(start_year, start_month, day_start)

    end_date = start_date + relativedelta(years=1) - relativedelta(days=1)

    return {
        "start_date": str(start_date),
        "end_date": str(end_date)
    }


def _safe_date(year, month, day):
    """Construit une date valide."""
    from datetime import date
    last_day = get_last_day(date(year, month, 1))
    if day > last_day.day:
        day = last_day.day
    return date(year, month, day)


def cint(val):
    """Convertit une valeur en entier."""
    return int(val or 0)
