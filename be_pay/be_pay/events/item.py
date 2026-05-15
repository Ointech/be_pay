import frappe

def before_save(doc, method=None):
    # --- from script: Last Attendance Sync Update ---
    s = frappe.get_doc('Shift Type','Morning')
    s.last_sync_of_checkin =  frappe.utils.add_to_date(frappe.utils.today(), days=-1, as_string=True) + ' 23:59:59'
    s.save()

    s = frappe.get_doc('Shift Type','Night')
    s.last_sync_of_checkin =  frappe.utils.add_to_date(frappe.utils.today(), days=-3, as_string=True) + ' 23:59:59'
    s.save()


    # --- from script: Conge Automatique ---
    employees = frappe.db.get_list(doctype = "Employee", 
        fields = ["name","conge_days","conge_days_5_years","date_of_joining","employee_category_details"], 
        filters = {"Status" : "Active"}
    )
    for e in employees : 
        date_join = frappe.utils.getdate(e.date_of_joining) 
        year_join = int(str(date_join)[:4])
        next_5_years = year_join
        today = frappe.utils.getdate()
        year_today = int(frappe.utils.get_date_str(today)[:4])
        diff = year_today - year_join
        if (diff % 5) == 0 :
            mois_join = str(date_join)[5:7]
            mois_today = frappe.utils.get_date_str(today)[5:7]
            if mois_join == mois_today : # todo utiliser date between plutot
                employee = frappe.get_doc("Employee", e.name)
                #category = frappe.get_doc("Employee Category Details",employee.employee_category_details)
                conge_days_5_years = frappe.db.get_single_value("Payroll Settings", "conge_days_5_years")
                employee.conge_days_5_years = (diff // 5) * conge_days_5_years
                employee.save()
                #nb_jours = (diff // 5) * 2
                #frappe.msgprint(str(conge_days_5_years))


    # --- from script: shift-marking-for-loop ---
    filters = {'name':'EMP-CKIN-06-2022-054605'}
    ck_list = frappe.get_list('Employee Checkin', ['*'], filters=filters)

    #frappe.msgprint(str(ck_list))

    for e in ck_list:


        punch = (e.time).split(" ")[1]
        punchdate = (e.time).split(" ")[0]
        hour = int(punch.split(":")[0])
        log_type = e.log_type
        shift_type = e.shift
        morningin = range(5,12)
        nightin = range(16,22)
        morningout = range(16,23)
        nightout = range(7,12)


        shift_start_time_morning = ' 08:00:01'
        shift_start_morning =punchdate + shift_start_time_morning
        actual_shift_start_time_morning =' 06:00:00'
        actual_shift_start_morning =punchdate + actual_shift_start_time_morning

        shift_end_time_morning = ' 18:00:00'
        shift_end_morning = punchdate + shift_end_time_morning
        actual_shift_end_time_morning = ' 22:00:00'
        actual_shift_end_morning = punchdate + actual_shift_end_time_morning

        shift_start_time_night = ' 18:00:01'
        shift_start_night = punchdate + shift_start_time_night
        actual_shift_start_time_night = ' 16:00:00'
        actual_shift_start_night = punchdate + actual_shift_start_time_night

        shift_end_time_night = ' 08:00:00'
        shift_end_night = punchdate + shift_end_time_night
        actual_shift_end_time_night = ' 12:00:00'
        actual_shift_end_night = punchdate + actual_shift_end_time_night


        ck = frappe.get_doc('Employee Checkin', e.name)
        if log_type == 'IN' and hour in morningin and shift_type is None:
            ck.shift = 'Morning';
        elif log_type == 'IN' and hour in nightin and shift_type is None:
            ck.shift = 'Night';
        elif log_type == 'OUT' and hour in morningout and shift_type is None:
            ck.shift = 'Morning';
        elif log_type == 'OUT' and hour in nightout and shift_type is None:
            ck.shift = 'Night';




