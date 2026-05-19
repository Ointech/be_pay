frappe.ui.form.on("Pay Bonus Provision", {
	setup: function(frm) {
		console.log("[Pay Bonus Provision] set_query enregistré pour employee / pay_employee_table");

		frm.set_query("employee", "pay_employee_table", function(doc, cdt, cdn) {
			console.log("[Pay Bonus Provision] Filtre employee déclenché pour ligne", cdn);
			return {
				query: "be_pay.be_pay.doctype.pay_bonus_provision.pay_bonus_provision.get_bonus_employees"
			};
		});
	}
});
