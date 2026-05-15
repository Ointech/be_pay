import frappe

def before_insert(doc, method=None):
    # --- from script: Attendances insert ---
    to_date = frappe.utils.getdate(doc.attendance_date)
    current_day = f"{to_date.day:02d}"  # Jour sur deux chiffres
    current_month = f"{to_date.month:02d}"  # Mois sur deux chiffres
    current_year = to_date.year  # Année entière (quatre chiffres)
    current_year_deux = str(current_year)[-2:]  # Deux derniers chiffres de l'année

    #frappe.msgprint(f"Compare date and { result[0].attendance_date}")

    if to_date:

        # Récupérer l'employé
        employee = doc.employee

        # Construire le naming series personnalisé
        doc.naming_series = f"{current_year_deux}-{employee}-{current_year}-{current_month}-{current_day}"

        # Générer le nom automatiquement
        doc.name = doc.naming_series


def before_save(doc, method=None):
    # --- from script: Save Attendance ---
    to_date = frappe.utils.getdate(doc.attendance_date)
    current_date = frappe.utils.getdate(doc.attendance_date)
    current_date = frappe.utils.add_days(current_date, -7)

    while current_date <= to_date:
        # Créer une instance de Attendance List

        Query = """
            select * from `tabHoliday` where holiday_date = %s and weekly_off = 1
        """
        results = frappe.db.sql(Query,(current_date), as_dict=True)

        if results :

            Quer = """
                select * from `tabAttendance` where attendance_date = %s and employee = %s
            """
            result = frappe.db.sql(Quer,(results[0].holiday_date,doc.employee), as_dict=True)

            if result :
                #frappe.msgprint(f"Compare date == {results[0].holiday_date} and { result[0].attendance_date}")
                if results[0].holiday_date == result[0].attendance_date :
                #to_date = frappe.utils.getdate(doc.attendance_date)
                    #frappe.msgprint(f"Date Presence Trouvé == {results[0].holiday_date}")

                    attendance_list = frappe.new_doc('Attendance')
                else:
                    #frappe.msgprint(f"Date Presence Non == {results[0].holiday_date}")

                    attendance_list = frappe.new_doc('Attendance')

                    # Remplir les champs principaux
                    attendance_list.employee = doc.employee
                    attendance_list.employee_name = doc.employee_name
                    attendance_list.status = "Present"
                    attendance_list.attendance_date = current_date
                    attendance_list.company = doc.company
                    attendance_list.department = doc.department
                    attendance_list.shift = "O"

                    # Sauvegarder et soumettre l'Attendance List
                    attendance_list.save()
                    attendance_list.submit()

            # Passer au jour suivant
        current_date = frappe.utils.add_days(current_date, 1)

    #frappe.throw(f"Date Presence == {current_date}")

