import frappe


def after_install():
    """
    Crée automatiquement :
    - Le Salary Component 'Air Ticket' s'il n'existe pas.
    - Les 4 Shift Types standards (Matin, Midi, Soir, Nuit) avec 8h de travail.
    """
    # ------------------------------------------------------------------
    # Salary Component "Air Ticket"
    # ------------------------------------------------------------------
    if not frappe.db.exists("Salary Component", "Air Ticket"):
        doc = frappe.new_doc("Salary Component")
        doc.name = "Air Ticket"
        doc.salary_component = "Air Ticket"
        doc.salary_component_abbr = "AIRTIC"
        doc.type = "Earning"
        doc.is_on_gift_salary = 1
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    # ------------------------------------------------------------------
    # Shift Types standards (8h chacun)
    # ------------------------------------------------------------------
    shift_types = [
        {"name": "Matin", "start_time": "07:00:00", "end_time": "15:00:00"},
        {"name": "Midi", "start_time": "11:00:00", "end_time": "19:00:00"},
        {"name": "Soir", "start_time": "15:00:00", "end_time": "23:00:00"},
        {"name": "Nuit", "start_time": "23:00:00", "end_time": "07:00:00"},
    ]

    for shift in shift_types:
        if not frappe.db.exists("Shift Type", shift["name"]):
            doc = frappe.new_doc("Shift Type")
            doc.name = shift["name"]
            doc.start_time = shift["start_time"]
            doc.end_time = shift["end_time"]
            doc.enable_auto_attendance = 0
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
