// --- Script for Leave Application ---
frappe.ui.form.on('Leave Application', {
	employee: function(frm) {
		frm.trigger("make_dashboard2");
	},
	from_date: function(frm) {
		frm.trigger("make_dashboard2");
	},
	to_date: function(frm) {
		frm.trigger("make_dashboard2");
	},
	
	make_dashboard2: function(frm) {
		var leave_details;
		let all_leaves;
		if (frm.doc.employee) {
			frm.set_query('leave_type', function() {
				return {
					filters: [
						['leave_type_name', '!=', 'zzz']
					]
				};
			});
		}
	},
})

// --- Script for Leave Application ---
frappe.ui.form.on('Leave Application', {
  refresh(frm) {
  // Votre code ici (si nécessaire)
  },
 
  before_save: function(frm) {
  let start_date = frm.doc.from_date;
  let end_date = frm.doc.to_date;
  
  let start_date_obj = new Date(start_date);
  let end_date_obj = new Date(end_date);
  
  // Calculer la différence en jours entre les deux dates
  let timeDiff = end_date_obj - start_date_obj;
  let totalDays = Math.ceil(timeDiff / (1000 * 60 * 60 * 24)) + 1; // +1 pour inclure le jour de départ
 
  // Vérifier chaque date dans la table custom_jours_off, si elle existe
  let validDaysOff = 0;
  if (frm.doc.custom_jours_off && frm.doc.custom_jours_off.length > 0) { // Vérifier si le tableau n'est pas vide
  for (let i = frm.doc.custom_jours_off.length - 1; i >= 0; i--) {
  let row = frm.doc.custom_jours_off[i];
  let row_date = new Date(row.date_day_off);
  
  if (row_date < start_date_obj || row_date > end_date_obj) {
  frm.doc.custom_jours_off.splice(i, 1);
  frappe.msgprint(__("La date " + row.date_day_off + " ne se trouve pas dans la période délimitée. Veuillez choisir une autre date."));
  } else {
  validDaysOff++; // Compter les jours valides dans la période
  }
  } 
  }
 
  // Calculer le nombre de jours de congé en soustrayant les jours valides
  let leaveDays = totalDays - validDaysOff;
 
  // Afficher le nombre de jours de congé calculé
  // frappe.msgprint(__("Nombre de jours de congé calculé : " + leaveDays));
  frm.set_value('total_leave_days', leaveDays);
 
  // Rafraîchir le champ pour refléter les modifications
  frm.refresh_field('custom_jours_off');
  }
 });
 

