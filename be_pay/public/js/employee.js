// --- Script for Employee - Gestion des dépendants ---
frappe.ui.form.on('Employee', {
    refresh: function(frm) {
        if (frm.doc.dependant && frm.doc.dependant.length <= 0) {
            frm.get_field('dependant').grid.cannot_add_rows = true;
        } else {
            frm.get_field('dependant').grid.cannot_add_rows = false;
        }
        
        if (frm.doc.dependant && frm.doc.dependant.length > 0) {
            var first_row = frm.doc.dependant[0];
            if (first_row) {
                frappe.model.set_value(first_row.doctype, first_row.name, 'code', first_row.code);
                frappe.model.set_value(first_row.doctype, first_row.name, 'type', first_row.type);
                frappe.model.set_value(first_row.doctype, first_row.name, 'nom_complet', first_row.nom_complet);
                frm.refresh_field('dependant');
            }
        }
    },
    
    after_save: function(frm) {
        if (frm.doc.dependant && frm.doc.dependant.length <= 0) {
            frm.events.get_employee_dependant(frm);
        }
    },
    
    get_employee_dependant: function(frm) {
        return frappe.call({
            method: 'paie.override.employee.get_employee_dependant',
            args: {
                "emp_name": frm.doc.name,
            },
            callback: function(r) {
                if (r.message) {
                    var row = frm.add_child('dependant');
                    row.code = r.message.employee;
                    row.type = 'Employee';
                    row.nom_complet = r.message.employee_name;
                    row.date_naissance = r.message.date_of_birth;
                    frm.refresh_field('dependant');
                    frm.dirty();
                }
            }
        });
    }
});

// --- Script for Employee - Dependant removal ---
frappe.ui.form.on('Dependent', {
    before_dependant_remove: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.idx == 1) {
            frappe.throw(__("Employee cannot be removed"));
        }
    },
    
    type: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.idx != 1 && row.type == "Employee") {
            frappe.throw(__("Cannot select 'Employee'!!!"));
        }
    }
});

// --- Script for Employee - Category details ---
frappe.ui.form.on('Employee', {
    employee_category_details: function(frm) {
        if (!frm.doc.employee_category_details) return;
        
        frappe.db.get_doc("Pay Employee Category Detail", frm.doc.employee_category_details).then(r => {
            frm.set_value('conge_days', r.conge_days);
            frm.set_value('basic_salary_per_day', r.pay_basic_salary_per_day);
            frm.set_value('basic_salary_per_hour', r.basic_salary_per_hour);
            frm.set_value('logement', r.pay_housing);
            frm.set_value('transport', r.pay_transport);
            frm.set_value('conge_days_final_settlement', r.conge_days_final_settlement);
            frm.set_value('conge_year_final_settlement', r.conge_year_final_settlement);
            frm.dirty();
            frm.refresh();
        });
    }
});

// --- Script for Employee - Contrat Projet ---
frappe.ui.form.on('Employee', {
    refresh: function(frm) {
        // if (!frm.is_new() && frm.doc.employee) {
        //     frappe.db.get_value("Contrat Projet", {'parent': frm.doc.employee}, "code_projet", (r) => {
        //         if (r && r.code_projet) {
        //             frm.set_value('code_projet', r.code_projet);
        //         }
        //     });
        // }
    },
    
    before_save: function(frm) {
        if (!frm.doc.custom_idgo4hr && frm.doc.custom_contrat_projet && frm.doc.custom_contrat_projet.length > 0) {
            var date_ajuste = frappe.datetime.get_today();
            var child_row = frm.doc.custom_contrat_projet[frm.doc.custom_contrat_projet.length - 1];
            
            if (child_row) {
                frm.set_value('department', child_row.code_projet);
                frm.set_value('scheduled_confirmation_date', child_row.date_debut);
                frm.set_value('contract_end_date', child_row.date_fin);
                frm.set_value('projet', child_row.code_projet);
                frm.set_value('date_entree', child_row.date_debut);
                frm.set_value('date_actuelle', date_ajuste);
            }
        }
    }
});

// --- Script for Employee - Départ ---
frappe.ui.form.on('Employee', {
    depart: function(frm) {
        if (frm.doc.anciennete) {
            let preavis_et_anciennete = Math.ceil(frm.doc.anciennete / 2);
            frm.set_value('preavis_et_anciennete', preavis_et_anciennete);
        }
    }
});

// --- Script for Employee - Provision ---
frappe.ui.form.on('Employee', {
    refresh: function(frm) {
        if (frm.is_new()) return;
        
        frm.add_custom_button(
            __("Provision"),
            function() {
                let d = new frappe.ui.Dialog({
                    title: 'Mise à jour Provision',
                    fields: [
                        {
                            label: 'Fiscal Year',
                            fieldname: 'fiscal_year',
                            fieldtype: 'Link',
                            options: "Fiscal Year",
                            on_change: function() {
                                let fiscal_year = d.get_value('fiscal_year');
                                if (fiscal_year) {
                                    frappe.db.get_doc("Fiscal Year", fiscal_year).then(r => {
                                        d.set_value('debut', r.start_date);
                                        d.set_value('fin', r.end_date);
                                    });
                                }
                            }
                        },
                        {
                            label: 'Leave Type',
                            fieldname: 'leave_type',
                            fieldtype: 'Link',
                            options: 'Leave Type',
                            get_query: function() {
                                return {
                                    filters: {
                                        'is_on_provision': 1
                                    }
                                };
                            }
                        }
                    ],
                    primary_action_label: __('Mettre à jour'),
                    primary_action: function(values) {
                        if (!values.fiscal_year || !values.leave_type) {
                            frappe.msgprint(__("Please select both Fiscal Year and Leave Type"));
                            return;
                        }
                        
                        frappe.call({
                            method: "fleuve_congo_custom.fleuve_congo_custom.doctype.provision.provision.update_provision_details",
                            args: {
                                fiscal_year: values.fiscal_year,
                                leave_type: values.leave_type,
                                emp_name: frm.doc.name,
                                employment_type: frm.doc.employment_type,
                            },
                            callback: function(r) {
                                if (r && !r.exc) {
                                    frappe.msgprint(__("Provision Mise à Jour effectuée avec succès"));
                                }
                            }
                        });
                        d.hide();
                    }
                });
                d.show();
            },
            __("Actions")
        );
    }
});

// --- Script for Employee - Salaire et catégorie ---
frappe.ui.form.on('Employee', {
    onload: function(frm) {
        frm.set_value('salaire_old', frm.doc.salaire_de_base);
        frm.set_value('employee_category_old', frm.doc.employee_category_details);
    },
    
    before_save: function(frm) {
        if (!frm.doc.salaire_de_base || frm.doc.salaire_de_base <= 0) {
            return;
        }
        
        var salaireBase = frm.doc.salaire_de_base / 26;
        var salaireMoyen = salaireBase;
        var categorie_true;
        
        // Détermination de la catégorie basée sur le salaire moyen
        if (salaireMoyen <= 5) {
            categorie_true = "MAO1-1.I";
        } else if (salaireMoyen > 5 && salaireMoyen <= 5.8) {
            categorie_true = "MAL1-2.I";
        } else if (salaireMoyen > 5.8 && salaireMoyen <= 6.65) {
            categorie_true = "TSP0-3.II";
        } else if (salaireMoyen > 6.65 && salaireMoyen <= 7.7) {
            categorie_true = "TSQ1-4.III";
        } else if (salaireMoyen > 7.7 && salaireMoyen <= 8.9) {
            categorie_true = "TSQ2-5.III";
        } else if (salaireMoyen > 8.9 && salaireMoyen <= 10.3) {
            categorie_true = "TSQ3-6.III";
        } else if (salaireMoyen > 10.3 && salaireMoyen <= 11.85) {
            categorie_true = "TRQ1-7.IV";
        } else if (salaireMoyen > 11.85 && salaireMoyen <= 13.7) {
            categorie_true = "TRQ2-8.IV";
        } else if (salaireMoyen > 13.7 && salaireMoyen <= 15.85) {
            categorie_true = "THQ0-9.V";
        } else if (salaireMoyen > 15.85 && salaireMoyen <= 18.30) {
            categorie_true = "MAT1-10.M";
        } else if (salaireMoyen > 18.3 && salaireMoyen <= 21.10) {
            categorie_true = "MAT2-11.M";
        } else if (salaireMoyen > 21.1 && salaireMoyen <= 24.4) {
            categorie_true = "MAT3-12.M";
        } else if (salaireMoyen > 24.4 && salaireMoyen <= 28.2) {
            categorie_true = "MAT4-13.M";
        } else if (salaireMoyen > 28.2 && salaireMoyen <= 32.55) {
            categorie_true = "CAC1-14.CC";
        } else if (salaireMoyen > 32.55 && salaireMoyen <= 37.6) {
            categorie_true = "CAC2-15.CC";
        } else if (salaireMoyen > 37.6 && salaireMoyen <= 43.4) {
            categorie_true = "CAC3-16.CC";
        } else if (salaireMoyen > 43.4 && salaireMoyen <= 50) {
            categorie_true = "CAC4-17.CC";
        } else {
            categorie_true = "CAD";
        }
        
        var categorie = categorie_true;
        var salaire = frm.doc.salaire_de_base;
        var date_ajuste = frappe.datetime.get_today();
        
        // Calcul de la date de paie
        var date_pay = frm.events.calculate_pay_date(frm, date_ajuste);
        
        // Gestion du tableau salaire_employee
        if (!frm.doc.salaire_old) {
            if (frm.doc.salaire_de_base > 0) {
                frm.set_value('salaire_old', frm.doc.salaire_de_base);
                var child = frm.add_child('salaire_employee');
                frappe.model.set_value(child.doctype, child.name, 'date_ajuste', date_ajuste);
                frappe.model.set_value(child.doctype, child.name, 'categorie', categorie);
                frappe.model.set_value(child.doctype, child.name, 'salaire', salaire);
                frappe.model.set_value(child.doctype, child.name, 'date_debut', date_pay);
                frm.refresh_field('salaire_employee');
            }
        } else {
            if (frm.doc.salaire_employee && frm.doc.salaire_employee.length > 0) {
                var child_row = frm.doc.salaire_employee[frm.doc.salaire_employee.length - 1];
                
                if (frm.doc.salaire_de_base != frm.doc.salaire_old) {
                    // Mettre à jour la date de fin de la dernière entrée
                    var today = new Date();
                    today.setDate(today.getDate() - 1);
                    var year = today.getFullYear();
                    var month = ('0' + (today.getMonth() + 1)).slice(-2);
                    var day = ('0' + today.getDate()).slice(-2);
                    var date_fin = year + '-' + month + '-' + day;
                    
                    frappe.model.set_value(child_row.doctype, child_row.name, 'date_fin', date_fin);
                    
                    // Ajouter nouvelle entrée
                    frm.set_value('salaire_old', frm.doc.salaire_de_base);
                    var new_child = frm.add_child('salaire_employee');
                    frappe.model.set_value(new_child.doctype, new_child.name, 'date_ajuste', date_ajuste);
                    frappe.model.set_value(new_child.doctype, new_child.name, 'categorie', categorie);
                    frappe.model.set_value(new_child.doctype, new_child.name, 'salaire', salaire);
                    frappe.model.set_value(new_child.doctype, new_child.name, 'date_debut', date_pay);
                    frm.refresh_field('salaire_employee');
                }
            } else {
                // Ajouter première entrée
                var new_child = frm.add_child('salaire_employee');
                frappe.model.set_value(new_child.doctype, new_child.name, 'date_ajuste', date_ajuste);
                frappe.model.set_value(new_child.doctype, new_child.name, 'categorie', categorie);
                frappe.model.set_value(new_child.doctype, new_child.name, 'salaire', salaire);
                frappe.model.set_value(new_child.doctype, new_child.name, 'date_debut', date_pay);
                frm.refresh_field('salaire_employee');
            }
        }
    },
    
    calculate_pay_date: function(frm, date_ajuste) {
        var date_joining = new Date(date_ajuste);
        var year = date_joining.getFullYear();
        var month = date_joining.getMonth() + 1;
        var day = date_joining.getDate();
        var date_pay = year + '-' + ('0' + month).slice(-2) + '-' + day;
        
        if (frm.doc.employment_type === 'Nationaux') {
            date_pay = year + '-' + ('0' + month).slice(-2) + '-' + '21';
        } else if (frm.doc.employment_type === 'Expatriés') {
            date_pay = year + '-' + ('0' + month).slice(-2) + '-' + '01';
        }
        
        return date_pay;
    }
});