import frappe

def before_save(doc, method=None):
    # --- from script: Test2 ---
    #frappe.msgprint(str(frappe.utils.get_datetime('2000-03-18 08:00:01')))
    punch = (doc.time).split(" ")[1]
    punchdate = (doc.time).split(" ")[0]
    hour = int(punch.split(":")[0])
    log_type = doc.log_type
    shift_type = doc.shift
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



    if log_type == 'IN' and hour in morningin and shift_type is None:
        doc.shift = "Morning"
        doc.shift_start = frappe.utils.get_datetime(shift_start_morning)
        doc.shift_end = frappe.utils.get_datetime(shift_end_morning)
        doc.shift_actual_start = frappe.utils.get_datetime(actual_shift_start_morning)
        doc.shift_actual_end = frappe.utils.get_datetime(actual_shift_end_morning)


    elif log_type == 'IN' and hour in nightin and shift_type is None:
        doc.shift = "Night"
        doc.shift_start = frappe.utils.get_datetime(shift_start_night)
        doc.shift_end = frappe.utils.get_datetime(shift_end_night)
        doc.shift_actual_start = frappe.utils.get_datetime(actual_shift_start_night)
        doc.shift_actual_end = frappe.utils.get_datetime(actual_shift_end_night)


    elif log_type == 'OUT' and hour in morningout and shift_type is None:
        doc.shift = "Morning"
        doc.shift_start = frappe.utils.get_datetime(shift_start_morning)
        doc.shift_end = frappe.utils.get_datetime(shift_end_morning)
        doc.shift_actual_start = frappe.utils.get_datetime(actual_shift_start_morning)
        doc.shift_actual_end = frappe.utils.get_datetime(actual_shift_end_morning)


    elif log_type == 'OUT' and hour in nightout and shift_type is None:
        doc.shift = "Night"
        doc.shift_start = frappe.utils.add_to_date(frappe.utils.get_datetime(shift_start_night),days=-1) 
        doc.shift_end = frappe.utils.get_datetime(shift_end_night)
        doc.shift_actual_start = frappe.utils.add_to_date(frappe.utils.get_datetime(actual_shift_start_night),days=-1)
        doc.shift_actual_end = frappe.utils.get_datetime(actual_shift_end_night)




