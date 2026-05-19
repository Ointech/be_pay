# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Salary Component pour Be Pay.
"""

import frappe
from frappe import _
from hrms.payroll.doctype.salary_component.salary_component import SalaryComponent


class CustomSalaryComponent(SalaryComponent):
    def on_trash(self):
        if self.name == "Air Ticket":
            frappe.throw(
                _(
                    "Le composant 'Air Ticket' est protégé et ne peut pas être supprimé."
                )
            )
        super().on_trash()
