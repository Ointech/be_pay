/**
 * Client Script pour Pay Payroll Settings (Be Pay)
 *
 * Filtre la table attendance_salary_components pour n'afficher que les
 * Salary Component dont custom_is_for_attendance est coché.
 */
frappe.ui.form.on("Pay Payroll Settings", {
	refresh: function (frm) {
		// Filtre sur le champ Link dans la table enfant
		frm.set_query("salary_component", "attendance_salary_components", function () {
			return {
				filters: {
					custom_is_for_attendance: 1,
				},
			};
		});
	},
});
