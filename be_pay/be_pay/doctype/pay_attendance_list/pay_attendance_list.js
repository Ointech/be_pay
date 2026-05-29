frappe.ui.form.on('Pay Attendance List', {
    refresh: function(frm) {
        // Filtrer salary_component dans les lignes selon Pay Payroll Settings
        frappe.call({
            method: 'be_pay.be_pay.doctype.pay_attendance_list.pay_attendance_list.get_allowed_salary_components',
            callback: function(r) {
                if (r.message && r.message.length) {
                    frm.set_query("salary_component", "attendance_line", function() {
                        return {
                            filters: {
                                name: ["in", r.message]
                            }
                        };
                    });
                }
            }
        });
    },

    pay_period: function(frm) {
        if (!frm.doc.pay_period) return;
        _update_pay_attendance_dates(frm);
    },

    company: function(frm) {
        if (!frm.doc.pay_period) return;
        _update_pay_attendance_dates(frm);
    },

    employment_type: function(frm) {
        if (!frm.doc.pay_period) return;
        _update_pay_attendance_dates(frm);
    }
});

function _update_pay_attendance_dates(frm) {
    console.log('Find');
    frappe.call({
        method: 'be_pay.overrides.attendance_sync.get_pay_attendance_dates',
        args: {
            pay_period: frm.doc.pay_period,
            company: frm.doc.company,
            employment_type: frm.doc.employment_type
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('start_date', r.message.start_date);
                frm.set_value('end_date', r.message.end_date);
            }
        },
        error: function(err) {
            console.error('get_pay_attendance_dates error', err);
        }
    });
}
