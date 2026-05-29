# Copyright (c) 2025, Be Pay
# License: MIT
"""
Synchronisation event-driven entre Attendance et Pay Attendance List.

Logique :
- À chaque création / modification / annulation d'une Attendance,
  cette module met à jour automatiquement le Pay Attendance List (PAL)
  actif pour l'employé concerné.
- Le PAL est déterminé par la période de paie active à la date de
  l'Attendance, en respectant la configuration Pay Payroll Settings :
  * Mode global    → utilise les bornes du Payroll Period standard
  * Mode par type  → utilise payroll_period_details(day_start, day_end)
- Un PAL est créé automatiquement s'il n'existe pas encore.
- Les lignes Pay Attendance Line agrègent les heures par Salary Component
  (via Shift Type.custom_salary_component).
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt, get_last_day
from dateutil.relativedelta import relativedelta
from collections import defaultdict


def sync_attendance_to_pay_list(doc, method):
    """
    Hook appelé on_submit / on_cancel / on_update_after_submit de Attendance.
    """
    if doc.status == "Absent":
        # On recalcule quand même pour mettre à jour les absences
        pass

    employee = doc.employee
    attendance_date = getdate(doc.attendance_date)

    pal = get_or_create_pay_attendance_list(employee, attendance_date)
    if not pal:
        frappe.logger().warning(
            "attendance_sync | Impossible de trouver/créer le PAL pour %s le %s",
            employee,
            attendance_date,
        )
        return

    recalculate_pay_attendance_line(pal.name, employee)

    # Marquer le PAL comme synchronisé
    frappe.db.set_value("Pay Attendance List", pal.name, "pay_find", 1)


# ---------------------------------------------------------------------------
# Détermination de la période active
# ---------------------------------------------------------------------------

def get_payroll_period_bounds(employee, attendance_date):
    """
    Retourne (start_date, end_date, payroll_period_name) pour un employé
    à une date donnée, en respectant la configuration Pay Payroll Settings.
    """
    emp = frappe.get_doc("Employee", employee)
    company = emp.company
    employment_type = emp.employment_type

    settings = frappe.get_single("Pay Payroll Settings")
    use_by_type = cint(settings.use_payroll_period_by_employment_type)

    if not use_by_type:
        return _get_global_period_bounds(attendance_date)

    # Mode par type d'emploi
    config = None
    for row in (settings.payroll_period_details or []):
        if row.employment_type == employment_type and row.company == company:
            config = row
            break

    if not config:
        frappe.logger().info(
            "attendance_sync | Aucune config pour %s / %s, fallback global",
            employment_type,
            company,
        )
        return _get_global_period_bounds(attendance_date)

    day_start = int(config.day_start or 1)
    day_end = int(config.day_end or 31)

    start_date, end_date = _calc_period_bounds(attendance_date, day_start, day_end)

    # Chercher un Payroll Period qui contient cette période
    pp = frappe.get_all(
        "Payroll Period",
        filters={
            "start_date": ("<=", start_date),
            "end_date": (">=", end_date),
        },
        fields=["name", "start_date", "end_date"],
        limit=1,
    )
    if pp:
        return start_date, end_date, pp[0].name

    # Fallback Fiscal Year
    fy = frappe.get_all(
        "Fiscal Year",
        filters={
            "year_start_date": ("<=", start_date),
            "year_end_date": (">=", end_date),
        },
        fields=["name", "year_start_date", "year_end_date"],
        limit=1,
    )
    if fy:
        return start_date, end_date, fy[0].name

    return start_date, end_date, None


def _get_global_period_bounds(attendance_date):
    """Mode global : utilise le Payroll Period (ou Fiscal Year) natif."""
    d = getdate(attendance_date)

    pp = frappe.get_all(
        "Payroll Period",
        filters={
            "start_date": ("<=", d),
            "end_date": (">=", d),
        },
        fields=["name", "start_date", "end_date"],
        limit=1,
    )
    if pp:
        return pp[0].start_date, pp[0].end_date, pp[0].name

    fy = frappe.get_all(
        "Fiscal Year",
        filters={
            "year_start_date": ("<=", d),
            "year_end_date": (">=", d),
        },
        fields=["name", "year_start_date", "year_end_date"],
        limit=1,
    )
    if fy:
        return fy[0].year_start_date, fy[0].year_end_date, fy[0].name

    return None, None, None


def _calc_period_bounds(for_date, day_start, day_end):
    """
    Calcule les bornes de la période mensuelle qui contient for_date.
    """
    from datetime import date
    d = getdate(for_date)
    if day_start <= day_end:
        start = _safe_date(d.year, d.month, day_start)
        end = _safe_date(d.year, d.month, day_end)
    else:
        if d.day >= day_start:
            start = _safe_date(d.year, d.month, day_start)
            next_m = d + relativedelta(months=1)
            end = _safe_date(next_m.year, next_m.month, day_end)
        else:
            prev_m = d - relativedelta(months=1)
            start = _safe_date(prev_m.year, prev_m.month, day_start)
            end = _safe_date(d.year, d.month, day_end)
    return start, end


def _safe_date(year, month, day):
    """Construit une date valide en ajustant le jour si hors limites du mois."""
    from datetime import date
    last = get_last_day(date(year, month, 1))
    if day > last.day:
        day = last.day
    return date(year, month, day)


# ---------------------------------------------------------------------------
# Gestion du Pay Attendance List
# ---------------------------------------------------------------------------

def get_or_create_pay_attendance_list(employee, attendance_date):
    """
    Trouve ou crée le Pay Attendance List actif pour un employé à une date donnée.
    """
    start_date, end_date, pp_name = get_payroll_period_bounds(
        employee, attendance_date
    )
    if not start_date or not end_date:
        return None

    emp = frappe.get_doc("Employee", employee)
    settings = frappe.get_single("Pay Payroll Settings")
    use_by_type = cint(settings.use_payroll_period_by_employment_type)

    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "company": emp.company,
    }
    if pp_name and frappe.db.exists("Payroll Period", pp_name):
        filters["pay_period"] = pp_name
    if use_by_type:
        filters["employment_type"] = emp.employment_type

    existing = frappe.get_all(
        "Pay Attendance List", filters=filters, fields=["name"], limit=1
    )
    if existing:
        return frappe.get_doc("Pay Attendance List", existing[0].name)

    # Créer un nouveau PAL
    pal = frappe.new_doc("Pay Attendance List")
    pal.start_date = start_date
    pal.end_date = end_date
    pal.company = emp.company
    if pp_name and frappe.db.exists("Payroll Period", pp_name):
        pal.pay_period = pp_name
    if use_by_type:
        pal.employment_type = emp.employment_type
    pal.insert(ignore_permissions=True)
    return pal


# ---------------------------------------------------------------------------
# Recalcul d'une ligne
# ---------------------------------------------------------------------------

def recalculate_pay_attendance_line(pal_name, employee):
    """
    Recalcule les Pay Attendance Line pour un employé dans un PAL donné.
    """
    pal = frappe.get_doc("Pay Attendance List", pal_name)

    # Supprimer les anciennes lignes pour cet employé (préserver les lignes HS)
    pal.attendance_line = [
        row for row in (pal.attendance_line or [])
        if row.employee != employee or getattr(row, "is_overtime_line", 0)
    ]

    # Récupérer toutes les Attendance de l'employé dans la période
    attendances = frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "attendance_date": ["between", [pal.start_date, pal.end_date]],
            "docstatus": 1,
        },
        fields=[
            "name",
            "attendance_date",
            "shift",
            "custom_working_hours",
            "status",
        ],
    )

    if not attendances:
        pal.save(ignore_permissions=True)
        return

    # Agréger par Salary Component
    hours_by_component = defaultdict(float)
    days_by_component = defaultdict(int)
    absences_by_component = defaultdict(int)

    emp = frappe.get_doc("Employee", employee)

    for att in attendances:
        salary_component = None
        if att.shift:
            sc = frappe.db.get_value(
                "Shift Type", att.shift, "custom_salary_component"
            )
            if sc:
                salary_component = sc

        if not salary_component:
            # Fallback : si le shift name correspond à un Salary Component valide, l'utiliser
            if att.shift and frappe.db.exists("Salary Component", att.shift):
                salary_component = att.shift
            else:
                # Fallback final : utiliser un composant par défaut pour que
                # Frappe conserve la ligne enfant (les lignes avec Link vide
                # sont supprimées automatiquement).
                salary_component = _get_default_salary_component()

        if att.status == "Absent":
            absences_by_component[salary_component] += 1
        else:
            hours = flt(att.custom_working_hours or 0)
            hours_by_component[salary_component] += hours
            days_by_component[salary_component] += 1

    # Créer les lignes
    for sc, total_hours in hours_by_component.items():
        row = pal.append("attendance_line", {})
        row.employee = employee
        row.employee_name = emp.employee_name or ""
        row.salary_component = sc
        row.hours = round(total_hours, 2)
        row.days = days_by_component[sc]
        row.absences = absences_by_component[sc]
        row.company = emp.company
        row.employment_type = emp.employment_type

    # Lignes avec seulement des absences (pas d'heures)
    for sc, total_abs in absences_by_component.items():
        if sc not in hours_by_component:
            row = pal.append("attendance_line", {})
            row.employee = employee
            row.employee_name = emp.employee_name or ""
            row.salary_component = sc
            row.hours = 0.0
            row.days = 0
            row.absences = total_abs
            row.company = emp.company
            row.employment_type = emp.employment_type

    pal.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Batch : initialisation rétroactive
# ---------------------------------------------------------------------------

def rebuild_all_pay_attendance_lists(start_date=None, end_date=None):
    """
    Recrée tous les Pay Attendance List et leurs lignes pour une période donnée.
    Version optimisée : regroupe par (employé, période) pour éviter les
    recalculs redondants.
    """
    if not start_date:
        start_date = "2026-04-01"
    if not end_date:
        end_date = frappe.utils.today()

    # 1. Pré-charger la configuration
    settings = frappe.get_single("Pay Payroll Settings")
    use_by_type = cint(settings.use_payroll_period_by_employment_type)
    config_by_type = {}
    if use_by_type:
        for row in (settings.payroll_period_details or []):
            config_by_type[(row.employment_type, row.company)] = {
                "day_start": int(row.day_start or 1),
                "day_end": int(row.day_end or 31),
            }

    # 2. Pré-charger les employés
    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "company", "employment_type"],
    )
    emp_map = {e.name: e for e in employees}

    # 3. Récupérer toutes les Attendance dans la période
    attendances = frappe.get_all(
        "Attendance",
        filters={
            "attendance_date": ["between", [start_date, end_date]],
            "docstatus": 1,
        },
        fields=["employee", "attendance_date"],
        order_by="attendance_date asc",
    )

    # 4. Regrouper par (employee, période)
    from collections import defaultdict
    groups = defaultdict(list)  # key -> [dates]

    for att in attendances:
        emp = emp_map.get(att.employee)
        if not emp:
            continue

        d = getdate(att.attendance_date)
        if use_by_type:
            cfg = config_by_type.get((emp.employment_type, emp.company))
            if cfg:
                period_start, period_end = _calc_period_bounds(
                    d, cfg["day_start"], cfg["day_end"]
                )
            else:
                period_start, period_end = _get_global_period_bounds_for_date(d)
        else:
            period_start, period_end = _get_global_period_bounds_for_date(d)

        key = (att.employee, period_start, period_end)
        groups[key].append(d)

    total = len(groups)
    processed = 0
    errors = 0

    for (employee, period_start, period_end), dates in groups.items():
        try:
            # Créer le PAL si nécessaire
            emp = emp_map[employee]
            settings = frappe.get_single("Pay Payroll Settings")
            use_by_type = cint(settings.use_payroll_period_by_employment_type)

            filters = {
                "start_date": period_start,
                "end_date": period_end,
                "company": emp.company,
            }
            if use_by_type:
                filters["employment_type"] = emp.employment_type

            existing = frappe.get_all(
                "Pay Attendance List", filters=filters, fields=["name"], limit=1
            )
            if existing:
                pal_name = existing[0].name
            else:
                # Chercher le Payroll Period ou Fiscal Year
                pp = frappe.get_all(
                    "Payroll Period",
                    filters={
                        "start_date": ("<=", period_start),
                        "end_date": (">=", period_end),
                    },
                    fields=["name"],
                    limit=1,
                )
                pp_name = pp[0].name if pp else None

                pal = frappe.new_doc("Pay Attendance List")
                pal.start_date = period_start
                pal.end_date = period_end
                pal.company = emp.company
                pal.pay_period = pp_name
                if use_by_type:
                    pal.employment_type = emp.employment_type
                pal.insert(ignore_permissions=True)
                pal_name = pal.name

            # Recalculer une seule fois pour cet employé dans cette période
            recalculate_pay_attendance_line(pal_name, employee)
            processed += 1

            if processed % 50 == 0:
                frappe.db.commit()
                frappe.logger().info(
                    "rebuild_all_pay_attendance_lists | %s/%s groupes traités",
                    processed,
                    total,
                )

        except Exception:
            errors += 1
            frappe.logger().error(
                "rebuild_all_pay_attendance_lists | Erreur pour %s (%s -> %s)",
                employee,
                period_start,
                period_end,
                exc_info=True,
            )

    frappe.db.commit()
    frappe.logger().info(
        "rebuild_all_pay_attendance_lists | TERMINÉ : %s traités, %s erreurs sur %s groupes",
        processed,
        errors,
        total,
    )


def _get_global_period_bounds_for_date(d):
    """Retourne (start_date, end_date) du Payroll Period natif contenant d."""
    pp = frappe.get_all(
        "Payroll Period",
        filters={"start_date": ("<=", d), "end_date": (">=", d)},
        fields=["start_date", "end_date"],
        limit=1,
    )
    if pp:
        return pp[0].start_date, pp[0].end_date
    fy = frappe.get_all(
        "Fiscal Year",
        filters={"year_start_date": ("<=", d), "year_end_date": (">=", d)},
        fields=["year_start_date", "year_end_date"],
        limit=1,
    )
    if fy:
        return fy[0].year_start_date, fy[0].year_end_date
    return d.replace(day=1), get_last_day(d)


@frappe.whitelist()
def get_pay_attendance_dates(pay_period, company=None, employment_type=None):
    """
    Retourne les start_date / end_date pour un Pay Attendance List en fonction
    du Payroll Period choisi et de la configuration Pay Payroll Settings.
    """
    pp = frappe.get_doc("Payroll Period", pay_period)
    settings = frappe.get_single("Pay Payroll Settings")

    if not cint(settings.use_payroll_period_by_employment_type):
        return {"start_date": str(pp.start_date), "end_date": str(pp.end_date)}

    if company and employment_type:
        for row in settings.payroll_period_details or []:
            if row.employment_type == employment_type and row.company == company:
                day_start = int(row.day_start or 1)
                day_end = int(row.day_end or 31)
                start_date, end_date = _calc_period_bounds(pp.start_date, day_start, day_end)
                return {"start_date": str(start_date), "end_date": str(end_date)}

    # Fallback si pas de config trouvée
    return {"start_date": str(pp.start_date), "end_date": str(pp.end_date)}


def _get_default_salary_component():
    """
    Retourne un Salary Component valide à utiliser comme fallback
    quand un Shift Type n'a pas de custom_salary_component.
    """
    candidates = ["Heure Supplémentaire", "Basic"]
    for c in candidates:
        if frappe.db.exists("Salary Component", c):
            return c
    first = frappe.get_all("Salary Component", fields=["name"], limit=1)
    return first[0].name if first else None


def cint(val):
    return int(val or 0)
