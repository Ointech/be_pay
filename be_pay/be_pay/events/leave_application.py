import frappe

def before_submit(doc, method=None):
    # --- from script: Leave Off validate ---
    start_date = doc.from_date
    end_date = doc.to_date

    # Convertir les dates en objets datetime
    start_date_obj = frappe.utils.getdate(start_date)
    end_date_obj = frappe.utils.getdate(end_date)

    # Calculer la différence en jours entre les deux dates
    time_diff = end_date_obj - start_date_obj
    total_days = time_diff.days + 1  # +1 pour inclure le jour de départ

    # Vérifier chaque date dans la table custom_jours_off
    valid_days_off = 0
    for row in doc.custom_jours_off :  # Parcourir la liste en sens inverse

        row_date = frappe.utils.getdate(row.date_day_off)

        valid_days_off = valid_days_off + 1  # Compter les jours valides dans la période

    # Calculer le nombre de jours de congé en soustrayant les jours valides
    leave_days = total_days - valid_days_off

    # Afficher le nombre de jours de congé calculé
    #frappe.msgprint(_(f"Nombre de jours de congé calculé : {leave_days}"))
    doc.total_leave_days = leave_days



def after_save(doc, method=None):
    # --- from script: Leave Swit Off ---
    start_date = doc.from_date
    end_date = doc.to_date

    # Convertir les dates en objets datetime
    start_date_obj = frappe.utils.getdate(start_date)
    end_date_obj = frappe.utils.getdate(end_date)

    # Calculer la différence en jours entre les deux dates
    time_diff = end_date_obj - start_date_obj
    total_days = time_diff.days + 1  # +1 pour inclure le jour de départ

    # Vérifier chaque date dans la table custom_jours_off
    valid_days_off = 0
    for row in doc.custom_jours_off :  # Parcourir la liste en sens inverse

        row_date = frappe.utils.getdate(row.date_day_off)

        valid_days_off = valid_days_off + 1  # Compter les jours valides dans la période

    # Calculer le nombre de jours de congé en soustrayant les jours valides
    leave_days = total_days - valid_days_off

    # Afficher le nombre de jours de congé calculé
    #frappe.msgprint(_(f"Nombre de jours de congé calculé : {leave_days}"))
    doc.total_leave_days = leave_days



def after_submit(doc, method=None):
    # --- from script: Add Attendance ---
    from_date = frappe.utils.getdate(doc.from_date)
    to_date = frappe.utils.getdate(doc.to_date)
    current_date = from_date

    # Créer un tableau pour stocker les enregistrements d'assiduité
    attendance_records = []

    while current_date <= to_date:
        # Vérifier s'il y a un jour férié ou un jour de congé
        query_holiday = """
            SELECT * FROM `tabHoliday` WHERE holiday_date = %s AND weekly_off = 1
        """
        holiday_results = frappe.db.sql(query_holiday, (current_date,), as_dict=True)

        # Vérifier si un enregistrement de présence existe déjà pour cette date
        query_attendance = """
            SELECT name FROM `tabAttendance` 
            WHERE employee = %s AND attendance_date = %s AND shift = %s
        """
        attendance_exists = frappe.db.sql(query_attendance, 
                                          (doc.employee, current_date, 'O' if holiday_results else doc.leave_type), 
                                          as_dict=True)

        if attendance_exists:
            frappe.msgprint(f"L'assiduité pour l'employé {doc.employee} est déjà marquée pour la date {current_date}.")
        else:
            # Créer une instance de Attendance List
            attendance_list = frappe.new_doc('Attendance')

            # Remplir les champs principaux
            attendance_list.employee = doc.employee
            attendance_list.employee_name = doc.employee_name
            attendance_list.status = "On Leave"

            #if holiday_results:
               # attendance_list.leave_type = 'O'
                #attendance_list.shift = 'O'
            #else:
            attendance_list.leave_type = doc.leave_type
            attendance_list.shift = doc.leave_type

            attendance_list.leave_application = doc.name
            attendance_list.attendance_date = current_date
            attendance_list.company = doc.company
            attendance_list.department = doc.department

            # Ajouter l'enregistrement à la liste
            attendance_records.append(attendance_list)

        # Passer au jour suivant
        current_date = frappe.utils.add_days(current_date, 1)

    # Sauvegarder et soumettre tous les enregistrements
    for attendance in attendance_records:
        attendance.save()
        attendance.submit()

    # Message de confirmation
    frappe.msgprint("Tous les enregistrements de présence ont été créés avec succès.")


