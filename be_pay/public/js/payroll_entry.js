// Copyright (c) 2025, Be Pay
// License: MIT

frappe.ui.form.on("Payroll Entry", {
    refresh(frm) {
        apply_payroll_period_mode(frm);
    },

    payroll_period(frm) {
        if (!frm.doc.payroll_period) return;
        fill_dates(frm);
    },

    employment_type(frm) {
        if (!frm.doc.payroll_period || !frm.doc.employment_type) return;
        fill_dates(frm);
    },

    company(frm) {
        if (!frm.doc.payroll_period) return;
        fill_dates(frm);
    }
});

function apply_payroll_period_mode(frm) {
    frappe.call({
        method: "be_pay.utils.payroll_entry_utils.get_payroll_period_mode",
        callback: function(r) {
            if (r.message) {
                const is_active = r.message.use_payroll_period_by_employment_type == 1;
                frm.toggle_reqd("employment_type", is_active);
                frm.toggle_display("employment_type", is_active);
            }
        }
    });
}

function fill_dates(frm) {
    frappe.call({
        method: "be_pay.utils.payroll_entry_utils.get_dates_by_employment_type",
        args: {
            employment_type: frm.doc.employment_type,
            company: frm.doc.company,
            payroll_period: frm.doc.payroll_period
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value("start_date", r.message.start_date);
                frm.set_value("end_date", r.message.end_date);
            }
        }
    });
}