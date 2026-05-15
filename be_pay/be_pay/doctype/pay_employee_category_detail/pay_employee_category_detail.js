// Copyright (c) 2026, ebamadernis@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pay Employee Category Detail", {
    refresh(frm) {
        // Optionnel: appeler la fonction au refresh si nécessaire
        // set_salary_per_day(frm);
    },

    basic_salary: function(frm) {
        set_salary_per_day(frm);
    },
    
    currency: function(frm) {
        set_salary_per_day(frm);
    }
});

function set_salary_per_day(frm) {
    // Vérifier si basic_salary existe
    if (!frm.doc.basic_salary) {
        frappe.msgprint(__("Veuillez d'abord renseigner le salaire de base"));
        return;
    }

    // Vérifier si devise (currency) est définie
    if (!frm.doc.currency) {
        frappe.msgprint(__("Veuillez d'abord sélectionner la devise"));
        return;
    }

    // Appel pour récupérer le nombre de jours ouvrables
    frappe.call({
        method: "be_pay.be_pay.doctype.pay_employee_category_detail.pay_employee_category_detail.get_working_day",
        args: {
            "currency": frm.doc.currency  // Passer la devise comme paramètre
        },
        callback: function(r) {
            if (r.message && r.message.working_day) {
                let working_days = r.message.working_day;
                let basic_salary = frm.doc.basic_salary;
                
                // Calculer le salaire par jour
                let salary_per_day = basic_salary / working_days;
                
                // Arrondir à 2 décimales
                salary_per_day = Math.round(salary_per_day * 100) / 100;
                
                // Définir la valeur
                frm.set_value("basic_salary_per_day", salary_per_day);
                
                // Optionnel: Afficher un message de confirmation
                frappe.show_alert({
                    message: __("Salaire par jour calculé: {0}", [salary_per_day]),
                    indicator: "green"
                }, 3);
            } else {
                frappe.msgprint(__("Impossible de récupérer le nombre de jours ouvrables"));
            }
        },
        error: function(err) {
            frappe.msgprint(__("Erreur lors du calcul: {0}", [err.message]));
        }
    });
}