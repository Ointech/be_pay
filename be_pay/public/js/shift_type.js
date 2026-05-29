/**
 * Client Script pour Shift Type (Be Pay)
 *
 * Filtre le champ custom_salary_component pour n'afficher que les
 * Salary Component dont custom_is_for_attendance est coché.
 */
frappe.ui.form.on("Shift Type", {
	refresh: function (frm) {
		// Appliquer le filtre sur le champ Link
		frm.set_query("custom_salary_component", function () {
			return {
				filters: {
					custom_is_for_attendance: 1,
				},
			};
		});
	},
});
