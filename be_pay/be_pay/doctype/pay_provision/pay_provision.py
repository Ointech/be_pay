# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PayProvision(Document):
    def before_save(self):
        # --- from script: Provision create ---
        if self.employment_type == "Expatriés" :

            query = """
                    SELECT *
                    FROM `tabPay Bonus Provision`  WHERE fiscal_year = %s AND (docstatus = 1 OR docstatus = 0)
            """

            # Exécuter la requête SQL avec les paramètres
            results = frappe.db.sql(query, self.fiscal_year , as_dict=True)

            if results :
                for empl in results :
                    if empl.fiscal_year == 0 :
                        frappe.throw("Veuillez créer les pourcentage pour cette annéé")


