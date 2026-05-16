// // --- Script for Salary Slip ---
// frappe.ui.form.on('Salary Slip', {
// 	salary_type(frm) {
// 		// your code here
// 		frappe.db.get_value("Salary Structure", {"salary_type": frm.doc.salary_type, "docstatus": 1}, "name", (r) => {
// 			frm.set_value('salary_structure', r.name);
// 			frm.events.get_emp_and_working_day_details(frm);
// 		});
// 		//frm.doc.salary_structure 
// 	},
// });

