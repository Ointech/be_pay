// Copyright (c) 2026, ebamadernis@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pay Settings Leave Accrual", {

    apply_accrual_to_all_employment_types(frm) {
        if (frm.doc.apply_accrual_to_all_employment_types == 1) {
            frm.clear_table("leave_accrual_detail");
            frm.refresh_field("leave_accrual_detail");
        }
    },

    add(frm) {
        add_employment_type_accrual(frm);
    }
});


function add_employment_type_accrual(frm) {

    if (!frm.doc.employment_type) {
        frappe.msgprint("Please select Employment Type first.");
        return;
    }

    if (!frm.doc.monthly_leave_accrual_days) {
        frappe.msgprint("Please enter Monthly Leave Accrual Days first.");
        return;
    }

    let exists = (frm.doc.leave_accrual_detail || []).some(row => {
        return row.employment_type === frm.doc.employment_type;
    });

    if (exists) {
        frappe.msgprint(
            `Employment Type <b>${frm.doc.employment_type}</b> already exists in the table.`
        );
        return;
    }

    let row = frm.add_child("leave_accrual_detail");

    row.employment_type = frm.doc.employment_type;
    row.leave_accrual = frm.doc.monthly_leave_accrual_days;

    frm.refresh_field("leave_accrual_detail");

    frm.set_value("employment_type", "");
    frm.set_value("monthly_leave_accrual_days", 0);
}