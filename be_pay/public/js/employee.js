frappe.ui.form.on('Employee', {
    onload(frm) {
        // Initialise salairy_old avec le CTC actuel pour éviter
        // une fausse détection de changement à la première sauvegarde.
        if (!frm.doc.salairy_old && frm.doc.ctc) {
            frm.set_value('salairy_old', frm.doc.ctc);
        }
    },

    refresh(frm) {
        category_by(frm);
        update_family_details(frm);
        add_provision_buttons(frm);
    },

    ctc(frm) {
        category_by(frm);
    },

    employee_category_detail(frm) {
        category_by(frm);
    }
});


function add_provision_buttons(frm) {
    if (frm.is_new()) return;

    // Bouton : Mettre à jour Provision
    frm.add_custom_button(__('Provision'), function () {
        let d = new frappe.ui.Dialog({
            title: __('Mise à jour Provision'),
            fields: [
                {
                    label: __('Fiscal Year'),
                    fieldname: 'fiscal_year',
                    fieldtype: 'Link',
                    options: 'Fiscal Year',
                    reqd: 1
                },
                {
                    label: __('Leave Type'),
                    fieldname: 'leave_type',
                    fieldtype: 'Link',
                    options: 'Leave Type',
                    reqd: 1,
                    get_query: () => {
                        return {
                            filters: { is_on_provision: 1 }
                        };
                    }
                }
            ],
            primary_action_label: __('Mettre à jour'),
            primary_action(values) {
                frappe.call({
                    method: 'be_pay.be_pay.doctype.pay_provision.pay_provision.update_provision_for_employee',
                    args: {
                        fiscal_year: values.fiscal_year,
                        leave_type: values.leave_type,
                        emp_name: frm.doc.name,
                    },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Provision mise à jour'));
                        }
                    }
                });
                d.hide();
            }
        });
        d.show();
    }, __('Actions'));

    // Bouton : Initialiser Provision
    frm.add_custom_button(__('Initialiser Provision'), function () {
        let d = new frappe.ui.Dialog({
            title: __('Initialisation Provision'),
            fields: [
                {
                    label: __('Fiscal Year'),
                    fieldname: 'fiscal_year',
                    fieldtype: 'Link',
                    options: 'Fiscal Year',
                    reqd: 1
                }
            ],
            primary_action_label: __('Initialiser'),
            primary_action(values) {
                frappe.call({
                    method: 'be_pay.be_pay.doctype.pay_provision.pay_provision.init_provision_for_employee',
                    args: {
                        fiscal_year: values.fiscal_year,
                        emp_name: frm.doc.name,
                    },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Provision initialisée'));
                        }
                    }
                });
                d.hide();
            }
        });
        d.show();
    }, __('Actions'));
}


frappe.ui.form.on('Pay Family Details', {
    type(frm, cdt, cdn) {
        update_family_details(frm);
    },

    date_of_birth(frm, cdt, cdn) {
        update_family_details(frm);
    },

    pay_family_details_add(frm, cdt, cdn) {
        update_family_details(frm);
    },

    pay_family_details_remove(frm, cdt, cdn) {
        update_family_details(frm);
    }
});


// =============================================================================
// Catégorie / Salaire
// =============================================================================

function category_by(frm) {
    frappe.call({
        method: 'be_pay.overrides.employee.category_by',
        callback: function(r) {
            if (r.message) {

                if (r.message.auto_assign_employee_category_by_salary == 1) {
                    frm.toggle_reqd('ctc', true);
                    frm.toggle_reqd('employee_category_detail', false);

                    if (frm.doc.ctc) {
                        set_category_min_max(frm);
                    }

                } else {
                    frm.toggle_reqd('employee_category_detail', true);
                    frm.toggle_reqd('ctc', false);

                    if (frm.doc.employee_category_detail) {
                        set_category_salary(frm);
                    }
                }
            }
        }
    });
}


function set_category_min_max(frm) {
    frappe.call({
        method: 'be_pay.overrides.employee.set_category_min_max',
        args: {
            salary_ctc: frm.doc.ctc
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('employee_category_detail', r.message.name);
            }
        }
    });
}


function set_category_salary(frm) {
    frappe.call({
        method: 'be_pay.overrides.employee.set_category_salary',
        args: {
            category: frm.doc.employee_category_detail
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('ctc', r.message.basic_salary);
            }
        }
    });
}


// =============================================================================
// Détails familiaux — âge & bénéficiaire
// =============================================================================

function update_family_details(frm) {
    if (!frm.doc.pay_family_details || !frm.doc.pay_family_details.length) {
        return;
    }

    // Récupère dependent_age depuis Pay Payroll Settings (cache côté client)
    frappe.db.get_single_value('Pay Payroll Settings', 'dependent_age')
        .then(dependent_age_limit => {
            dependent_age_limit = parseFloat(dependent_age_limit || 0);
            let today = new Date();
            let count_child = 0;
            let count_dependent = 0;

            frm.doc.pay_family_details.forEach(row => {
                // --- Calcul de l'âge ------------------------------------
                let age = 0;
                if (row.date_of_birth) {
                    let dob = new Date(row.date_of_birth);
                    age = today.getFullYear() - dob.getFullYear();
                    let m = today.getMonth() - dob.getMonth();
                    if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
                        age--;
                    }
                }
                frappe.model.set_value(row.doctype, row.name, 'age', age);

                // --- Détermination du bénéficiaire ----------------------
                let beneficiary = 0;

                if (row.type === 'Dependent') {
                    beneficiary = 1;
                    count_dependent += 1;
                } else if (row.type === 'Child' || row.type === 'Others') {
                    if (dependent_age_limit && age < dependent_age_limit) {
                        beneficiary = 1;
                        if (row.type === 'Child') {
                            count_child += 1;
                        }
                    } else {
                        beneficiary = 0;
                    }
                }

                frappe.model.set_value(row.doctype, row.name, 'beneficiary', beneficiary);
            });

            // Mise à jour des compteurs sur Employee (en dehors du tableau)
            if (frm.fields_dict.child) {
                frm.set_value('child', count_child);
            }
            if (frm.fields_dict.dependent) {
                frm.set_value('dependent', count_child + count_dependent);
            }
        });
}
