# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Item pour Be Pay.

Gère la synchronisation des shift types pour le module de pointage.
"""

import frappe
from frappe import _
from erpnext.stock.doctype.item.item import Item


class CustomItem(Item):
    """
    Extension de la classe Item pour la logique Be Pay.
    """

    def before_save(self):
        """
        Avant sauvegarde : mise à jour des derniers sync de checkin.
        """
        self._be_pay_update_shift_sync()
        super().before_save()

    def _be_pay_update_shift_sync(self):
        """
        Met à jour les dates de dernière synchronisation des shifts
        pour le module de pointage.
        """
        try:
            morning_shift = frappe.get_doc("Shift Type", "Morning")
            morning_shift.last_sync_of_checkin = (
                frappe.utils.add_to_date(
                    frappe.utils.today(), days=-1, as_string=True
                ) + " 23:59:59"
            )
            morning_shift.save()
        except frappe.DoesNotExistError:
            pass

        try:
            night_shift = frappe.get_doc("Shift Type", "Night")
            night_shift.last_sync_of_checkin = (
                frappe.utils.add_to_date(
                    frappe.utils.today(), days=-3, as_string=True
                ) + " 23:59:59"
            )
            night_shift.save()
        except frappe.DoesNotExistError:
            pass

        # Mise à jour automatique des congés pour les employés actifs
        self._be_pay_update_employee_leave_days()

    def _be_pay_update_employee_leave_days(self):
        """
        Met à jour les jours de congé pour les employés actifs
        en fonction de leur ancienneté (tous les 5 ans).
        """
        employees = frappe.db.get_list(
            "Employee",
            fields=[
                "name",
                "conge_days",
                "conge_days_5_years",
                "date_of_joining",
                "employee_category_details"
            ],
            filters={"status": "Active"}
        )

        for emp in employees:
            if not emp.date_of_joining:
                continue

            date_join = frappe.utils.getdate(emp.date_of_joining)
            year_join = date_join.year
            today = frappe.utils.getdate()
            year_today = today.year
            diff = year_today - year_join

            if (diff % 5) == 0:
                mois_join = date_join.month
                mois_today = today.month
                if mois_join == mois_today:
                    try:
                        conge_days_5_years = frappe.db.get_single_value(
                            "Pay Payroll Settings", "conge_days_5_years"
                        )
                        employee = frappe.get_doc("Employee", emp.name)
                        employee.conge_days_5_years = (diff // 5) * conge_days_5_years
                        employee.save()
                    except Exception:
                        pass


def get_item_by_employee_category(employee_category):
    """
    Récupère les articles associés à une catégorie d'employé.

    Args:
        employee_category (str): Catégorie d'employé

    Returns:
        list: Liste des articles
    """
    return frappe.get_all(
        "Item",
        filters={
            "item_group": employee_category,
            "disabled": 0
        },
        fields=["name", "item_name", "item_group"]
    )
