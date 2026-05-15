// --- Script for Loan ---
frappe.ui.form.on('Loan', {
	currency: function (frm) {
		var company_currency;
		if (!frm.doc.company) {
			company_currency = erpnext.get_currency(frappe.defaults.get_default("Company"));
		} else {
			company_currency = erpnext.get_currency(frm.doc.company);
		}
		if (frm.doc.currency) {
			if (company_currency != frm.doc.currency) {
				frappe.call({
					method: "erpnext.setup.utils.get_exchange_rate",
					args: {
						from_currency: frm.doc.currency,
						to_currency: company_currency,
					},
					callback: function (r) {
						frm.set_value("exchange_rate", flt(r.message));
					}
				});
			} else {
				frm.set_value("exchange_rate", 1.0);
			}
		}
	},
});

