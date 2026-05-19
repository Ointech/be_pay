frappe.ui.form.on('Pay Provision', {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Mettre à jour'), function () {
                frappe.call({
                    method: 'be_pay.be_pay.doctype.pay_provision.pay_provision.update_pay_provision',
                    args: { name: frm.doc.name },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Provision mise à jour'));
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    },
    employment_type(frm) {
        if (!frm.doc.fiscal_year) return;
        fill_dates(frm);
    },
    is_external_report(frm) {
        frm.toggle_display('external_report_month', frm.doc.is_external_report);
        if (!frm.doc.is_external_report) {
            frm.set_value('external_report_month', '');
        }
    },

});


function fill_dates(frm) {
    frappe.call({
        method: "be_pay.be_pay.doctype.pay_provision.pay_provision.get_dates_by_employment_type",
        args: {
            employment_type: frm.doc.employment_type,
            company: frm.doc.company,
            fiscal_year: frm.doc.fiscal_year
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value("start_date", r.message.start_date);
                frm.set_value("end_date", r.message.end_date);
            }
        }
    });
}
