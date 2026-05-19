import frappe


def after_install():
    """
    Crée automatiquement le Salary Component 'Air Ticket' s'il n'existe pas.
    """
    if not frappe.db.exists("Salary Component", "Air Ticket"):
        doc = frappe.new_doc("Salary Component")
        doc.name = "Air Ticket"
        doc.salary_component = "Air Ticket"
        doc.salary_component_abbr = "AIRTIC"
        doc.type = "Earning"
        doc.is_on_gift_salary = 1
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
