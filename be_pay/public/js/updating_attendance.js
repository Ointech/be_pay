// --- Script for Updating Attendance ---
// NOTE: Le doctype "Updating Attendance" n'existe pas encore dans be_pay.
// Ce script nécessite la création de ce doctype (ou d'un doctype équivalent)
// avec les champs: employee, payroll_period, societe, et la child table details_updating_attendance.

frappe.ui.form.on('Updating Attendance', {
    refresh(frm) {
        $('.primary-action').prop('hidden', true);

        var button = frm.fields_dict.get_attendances.$wrapper.find('button');
        button.addClass('btn btn-primary text-white custom-button');

        // Ajouter des styles personnalisés pour l'état de survol
        $('head').append(`
            .custom-button:hover {
                background-color: #f1f1f1 !important;
                color: #007bff !important;
            }
        `);

        var button = frm.add_custom_button(__('Update Attendance'), function() {
            let fiend = 0;

            if (!frm.doc.employee || frm.doc.employee.trim() === '') {
                frappe.throw({
                    title: __('Erreur'),
                    indicator: 'red',
                    message: __('Le champ Employee est requis.')
                });
            } else {
                let payroll_period = frm.doc.payroll_period;
                let employee = frm.doc.employee;

                let processItem = function(item) {
                    return new Promise((resolve) => {
                        console.log(`employee : ${employee}`);
                        console.log(`Date: ${item.date}`);
                        console.log(`status: ${item.status}`);
                        console.log(`shift: ${item.shift}`);

                        frappe.call({
                            method: "be_pay.api.updating_attendance_save",
                            args: {
                                Employee: employee,
                                date: item.date,
                                present: item.status,
                                shift: item.shift,
                            },
                            callback: function(response) {
                                if (response.message && response.message.length > 0) {
                                    frappe.call({
                                        method: "be_pay.api.updating_attendance_check",
                                        args: {
                                            Employee: employee,
                                            date: item.date,
                                            present: item.status,
                                        },
                                        callback: function(response) {
                                            const data = response.message;
                                            if (!data || data.length === 0) {
                                                let doctype = "Attendance";
                                                let Attend = frappe.model.get_new_doc(doctype);

                                                Attend.employee = employee;
                                                Attend.attendance_date = item.date;
                                                Attend.company = frm.doc.societe;
                                                Attend.shift = item.shift;
                                                Attend.status = item.status;

                                                frappe.db.insert(Attend).then(function(doc) {
                                                    if (doc) {
                                                        frappe.call({
                                                            method: "frappe.client.submit",
                                                            args: {
                                                                doc: doc
                                                            },
                                                            callback: function(response) {
                                                                if (response.message) {
                                                                    fiend++;
                                                                    console.log(`Code operation: ${fiend}`);
                                                                } else {
                                                                    console.error('Erreur lors de la soumission du document.');
                                                                }
                                                                resolve();
                                                            },
                                                            error: function(err) {
                                                                console.error('Erreur lors de la soumission:', err);
                                                                resolve();
                                                            }
                                                        });
                                                    } else {
                                                        console.error('Erreur lors de l\'insertion du document.');
                                                        resolve();
                                                    }
                                                });
                                            } else {
                                                console.log(`Data already exists, skipping insertion.`);
                                                resolve();
                                            }
                                        },
                                        error: function(err) {
                                            console.error('Erreur lors de la vérification des codes:', err);
                                            resolve();
                                        }
                                    });
                                } else {
                                    console.error("La réponse du serveur est vide ou invalide.");
                                    resolve();
                                }
                            },
                            error: function(err) {
                                console.error('Erreur lors de la mise à jour des codes:', err);
                                resolve();
                            }
                        });
                    });
                };

                // Utiliser une boucle asynchrone pour traiter chaque élément séquentiellement
                (async function() {
                    for (let item of frm.doc.details_updating_attendance) {
                        await processItem(item);
                    }

                    console.log(`Résultat OK: ${fiend}`);
                    if (fiend > 0) {
                        let message = (fiend >= 2)
                            ? `${fiend} Enregistrements Modifiés`
                            : `${fiend} Enregistrement Modifié`;
                        frappe.msgprint(__(message));
                    }
                })();
            }
        });

        button.addClass('btn btn-primary text-white custom-update-attendance-btn');

        // Injecter le style personnalisé pour l'état de survol
        $('head').append(`
            .custom-update-attendance-btn:hover {
                background-color: #f1f1f1 !important;
                color: #007bff !important;
            }
        `);
    },

    get_attendances: function(frm) {
        // Vérifier si le champ 'societe' est renseigné
        if (!frm.doc.societe) return;

        // Effacer le tableau 'details_updating_attendance'
        frm.clear_table('details_updating_attendance');
        frm.refresh_field('details_updating_attendance');

        // Récupérer les valeurs des champs 'payroll_period' et 'employee'
        let payroll_period = frm.doc.payroll_period;
        let employee = frm.doc.employee;

        // Vérifier si le champ 'employee' est renseigné
        if (!employee || employee.trim() === '') {
            frappe.throw({
                title: __('Erreur'),
                indicator: 'red',
                message: __('Le champ Employee est requis.')
            });
        } else {
            // Appeler la méthode pour récupérer les dates de la période de paie
            frappe.call({
                method: "be_pay.api.get_payroll_period_date",
                args: {
                    'employee': employee,
                    'name': payroll_period
                },
                callback: function(r) {
                    console.log(r);

                    if (r.message && Array.isArray(r.message)) {
                        console.log(`Period: ${payroll_period}`);

                        // Récupérer les valeurs du tableau
                        let my_start = '01/12/1999';
                        let my_end = '01/12/2099';
                        let employment_type = r.message[2]; // Type d'emploi

                        if (employment_type === 'Expatriés') {
                            my_start = r.message[0]; // start_date_exp
                            my_end = r.message[1]; // end_date_exp
                        } else {
                            my_start = r.message[0]; // start_date
                            my_end = r.message[1]; // end_date
                        }

                        console.log(`my_start: ${my_start}`);
                        console.log(`my_end: ${my_end}`);
                        console.log(`r.message.employment_type: ${employment_type}`);

                        // Appeler la méthode pour récupérer les données d'assiduité
                        frappe.call({
                            method: "be_pay.api.get_attendances_data",
                            args: {
                                'employee': employee,
                            },
                            callback: function(response) {
                                const data = response.message;
                                if (data && data.length > 0) {
                                    // Ajouter les données d'assiduité au tableau
                                    data.forEach(function(item) {
                                        frm.add_child('details_updating_attendance', {
                                            'shift': item.shift,
                                            'date': item.attendance_date,
                                            'status': item.status
                                        });
                                    });
                                    frm.refresh_field('details_updating_attendance');
                                }
                            },
                            error: function(err) {
                                console.error('Erreur lors de la récupération des codes:', err);
                                frappe.msgprint(__('Erreur: {0}', [err]));
                            }
                        });
                    } else {
                        frappe.msgprint(__('Aucune donnée valide reçue.'));
                    }
                },
                error: function(err) {
                    console.error('Erreur lors de la récupération des transferts:', err);
                    frappe.msgprint(__('Erreur: {0}', [err]));
                }
            });
        }
    }
});
