# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Loan pour Be Pay.

Gère le nettoyage des écritures d'intérêt lors de l'annulation.
"""

import frappe
from frappe import _
from erpnext.loan_management.doctype.loan.loan import Loan


class CustomLoan(Loan):
    """
    Extension de la classe Loan pour la logique Be Pay.
    """

    def before_cancel(self):
        """
        Avant annulation : suppression des écritures d'intérêt associées.
        """
        self._be_pay_cancel_loan_interest_accruals()
        super().before_cancel()

    def _be_pay_cancel_loan_interest_accruals(self):
        """
        Annule et supprime les Process Loan Interest Accrual et
        Loan Interest Accrual liés à ce prêt.
        """
        # Process Loan Interest Accrual
        process_accruals = frappe.get_all(
            "Process Loan Interest Accrual",
            filters={"loan": self.name}
        )

        for pa in process_accruals:
            doc = frappe.get_doc("Process Loan Interest Accrual", pa.name)
            doc.db_set("docstatus", 0, commit=True)
            doc.delete()

        # Loan Interest Accrual
        interest_accruals = frappe.get_all(
            "Loan Interest Accrual",
            filters={"loan": self.name}
        )

        for ia in interest_accruals:
            doc = frappe.get_doc("Loan Interest Accrual", ia.name)
            doc.db_set("docstatus", 0, commit=True)
            doc.delete()


def get_employee_loan_balance(employee, loan_type=None):
    """
    Récupère le solde total des prêts d'un employé.

    Args:
        employee (str): ID de l'employé
        loan_type (str, optional): Type de prêt

    Returns:
        float: Solde total des prêts
    """
    filters = {
        "applicant": employee,
        "docstatus": 1,
        "status": ("in", ["Disbursed", "Partially Disbursed"])
    }

    if loan_type:
        filters["loan_type"] = loan_type

    total = frappe.db.get_all(
        "Loan",
        filters=filters,
        fields=["SUM(total_payment - total_amount_paid) as balance"]
    )

    return total[0].balance or 0 if total else 0
