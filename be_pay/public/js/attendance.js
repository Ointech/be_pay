// --- Script for Attendance ---
frappe.ui.form.on('Attendance', {
    employee: function(frm) {

		frm.set_query('shift', function() {
			return {
				filters: [
					['is_shift_leave', '=', 0]
				]
			};
		});
		
		if (frm.doc.shift && frm.doc.is_shift_leave === 0) {
            frm.set_value('shift', null);
            frappe.msgprint(__('Le champ Shift a été réinitialisé car il répond aux critères.'));
        }

    }

})

// --- Script for Attendance ---
frappe.listview_settings['Attendance'] = {
    onload: function(listview) {
        if (!listview.page.custom_buttons_added) {
            listview.page.custom_buttons_added = true;

            // Ajouter un bouton personnalisé dans la barre d'outils
            listview.page.add_inner_button(__('Actualiser Présences'), function() {
                let d = new frappe.ui.Dialog({
                    title: __('Actualiser Présence'),
                    fields: [
                        {
                            label: __('Actualisation'),
                            fieldname: 'actualisation',
                            fieldtype: 'Select',
                            options: ['Tous le monde', 'Individuel'],
                            default: 'Tous le monde',
                            change: function() {
                                let actualisation = this.get_value();
                                if (actualisation === 'Individuel') {
                                    d.set_df_property('employee', 'hidden', false);
                                } else {
                                    d.set_df_property('employee', 'hidden', true);
                                }
                            }
                        },
                        {
                            label: __('Employee'),
                            fieldname: 'employee',
                            fieldtype: 'Link',
                            options: 'Employee',
                            hidden: true, // Masquer par défaut
                            get_query: () => {
                                return {
                                    filters: {
                                        'status': 'Active'
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Mettre à jour'),
                    primary_action: function(values) {
                        if (values.actualisation === 'Individuel') {
                            if (!values.employee) {
                                frappe.msgprint(__('Veuillez sélectionner un employé.'));
                                return;
                            }

                            frappe.call({
                                method: "fleuve_congo_custom.fleuve_congo_custom.doctype.provision.provision.update_attendance_individuel",
                                args: {
                                    employee: values.employee,
                                },
                                callback: function(r) {
                                    if (!r.exc) {
                                        frappe.msgprint(__('Actualisation en cours pour l\'employé sélectionné.'));
                                        listview.refresh();
                                    }
                                }
                            });
                        } else {
                            frappe.call({
                                method: "fleuve_congo_custom.fleuve_congo_custom.doctype.provision.provision.update_attendance_all",
                                callback: function(r) {
                                    if (!r.exc) {
                                        frappe.msgprint(__('Actualisation en cours pour tous les employés.'));
                                        listview.refresh();
                                    }
                                }
                            });
                        }
                        d.hide();
                    }
                });

                d.show();
            });
        }
    }
};

// --- Script for Attendance ---
frappe.ui.form.on('Attendance', {
    refresh(frm) {
        // Utiliser l'événement 'refresh' au lieu de 'insert' pour s'assurer que le code s'exécute correctement
        if (frm.is_new()) { // Vérifier si le formulaire est en mode création
            frm.doc.naming_series = ""; // Réinitialiser le naming_series

            // Récupérer les valeurs nécessaires
            let employee = frm.doc.employee;
            let attendanceDate = frm.doc.attendance_date;

            // Extraire l'année, le mois et le jour de la date
            let year = attendanceDate.slice(2, 4); // YY
            let month = attendanceDate.slice(5, 7); // MM
            let day = attendanceDate.slice(8, 10); // DD

            // Construire le naming_series
            frm.doc.naming_series = `YY-${employee}-${day}${month}${year} 00:00:00`;

            // Rafraîchir le formulaire pour afficher les modifications
            frm.refresh_field('naming_series');
        }
    }
});

