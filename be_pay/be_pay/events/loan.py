import frappe

def before_cancel(doc, method=None):
    # --- from script: Cancel Loan ---
    # Process Loan Interest Accrual
    je = frappe.get_all('Process Loan Interest Accrual', filters={'loan': doc.name})

    if je:
        je_doc = frappe.get_doc('Process Loan Interest Accrual', je[0].name)
        je_doc.db_set('docstatus', 0, commit=True)
        je_doc.delete()

    # Loan Interest Accrual
    LoanInt = frappe.get_all('Loan Interest Accrual', filters={'loan': doc.name})

    if LoanInt:
        LoanInt_doc = frappe.get_doc('Loan Interest Accrual', LoanInt[0].name)
        LoanInt_doc.db_set('docstatus', 0, commit=True)
        LoanInt_doc.delete()


