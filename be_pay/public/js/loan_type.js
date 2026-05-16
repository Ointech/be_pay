// // --- Script for Loan Type ---
// frappe.ui.form.on('Loan Type', {
// 	onload: function(frm) {
// 		$.each(["penalty_income_account", "interest_income_account"], function (i, field) {
// 			frm.set_query(field, function () {
// 				return {
// 					"filters": {
// 						"company": frm.doc.company,
// 						"root_type": "Income",
// 						"is_group": 0
// 					}
// 				};
// 			});
// 		});

// 		$.each(["payment_account", "loan_account", "disbursement_account"], function (i, field) {
// 			frm.set_query(field, function () {
// 				return {
// 					"filters": [
//                         ["company", "=", frm.doc.company],
//                         ["root_type", "IN", ["Asset", "Liability"]],
//                         ["is_group", "=", 0]
//                     ]
// 				};
// 			});
// 		});
// 	}
// });



