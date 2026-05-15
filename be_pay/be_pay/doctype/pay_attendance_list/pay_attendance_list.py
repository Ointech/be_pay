# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class PayAttendanceList(Document):
    def before_save(self):
        # --- from script: Attendance Synchron (exec fallback) ---
        script = "if doc.pay_find == 0:\n  # Initialisation des variables\n  pay_a1 = 0\n  pay_a2 = 0\n  pay_a3 = 0\n  pay_a4 = 0\n  \n  All_Value = 0\n  \n  # R\u00e9cup\u00e9rer tous les employ\u00e9s\n  query = \"\"\"\n  SELECT *\n  FROM `tabEmployee`\n  \"\"\"\n  employees = frappe.db.sql(query, as_dict=True)\n  \n  for empl in employees:\n  # Requ\u00eate pour obtenir les absences pour un employ\u00e9 sp\u00e9cifique\n  pay_a1 = 0\n  pay_a2 = 0\n  pay_a3 = 0\n  pay_a4 = 0\n  save = 0\n  \n  query = \"\"\"\n  SELECT \n  SUM(CASE \n  WHEN st.shift_deux_absences = 1 THEN 2\n  ELSE 1\n  END) AS resultats,\n  a.employee\n  FROM `tabAttendance` a\n  JOIN `tabShift Type` st ON a.shift = st.name\n  WHERE a.employee = %s\n  AND a.docstatus = 1\n  AND a.pay_status = 'Absent'\n  AND a.attendance_date BETWEEN %s AND %s\n  \"\"\"\n  \n  attendance_results = frappe.db.sql(query, (empl.employee, doc.start_date, doc.end_date), as_dict=True)\n  \n  query = \"\"\"\n  SELECT \n  a.nombre\n  FROM `tabHeures supplementaire` a\n  WHERE a.employee = %s\n  AND a.docstatus = 1\n  AND a.date_jour BETWEEN %s AND %s\n  \"\"\"\n  Heures_results = frappe.db.sql(query, (empl.employee, doc.start_date, doc.end_date), as_dict=True)\n  \n  \n  date_time_string = frappe.utils.now()\n  \n  \n  start_date = frappe.utils.getdate(doc.start_date)\n  end_date = frappe.utils.getdate(doc.end_date) \n  save = 0\n \n  query = \"\"\"\n  SELECT \n  s.leave_type,\n  f.date_day_off,\n  s.from_date,\n  s.to_date,\n  COUNT(f.date_day_off) AS total_off,\n  CASE \n  WHEN s.from_date < %(start_date)s AND s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, %(start_date)s) + 1\n  WHEN s.from_date < %(start_date)s THEN DATEDIFF(s.to_date, %(start_date)s) + 1\n  WHEN s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, s.from_date) + 1\n  ELSE DATEDIFF(s.to_date, s.from_date) + 1\n  END AS total_days,\n  (CASE \n  WHEN s.from_date < %(start_date)s AND s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, %(start_date)s) + 1\n  WHEN s.from_date < %(start_date)s THEN DATEDIFF(s.to_date, %(start_date)s) + 1\n  WHEN s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, s.from_date) + 1\n  ELSE DATEDIFF(s.to_date, s.from_date) + 1\n  END - COUNT(f.date_day_off)) AS total_leave_days\n  FROM \n  `tabLeave Application` s\n  LEFT JOIN \n  `tabLeave Application Off` f\n  ON s.name = f.parent\n  WHERE \n  s.employee = %(employee)s\n  AND s.docstatus = 1\n  AND s.from_date <= %(end_date)s\n  AND s.to_date >= %(start_date)s\n  AND s.leave_type = %(leave_type)s\n  AND (f.date_day_off BETWEEN %(start_date)s AND %(end_date)s OR f.date_day_off IS NULL)\n  GROUP BY \n  s.leave_type\n  \"\"\"\n  \n  results = frappe.db.sql(query, {\n  \"employee\": empl.employee,\n  \"start_date\": start_date,\n  \"end_date\": end_date,\n  \"leave_type\": \"Mise \u00e0 pied\"\n  }, as_dict=True)\n  \n  # Si la table `Leave Application Off` ne contient pas de donn\u00e9es (r\u00e9sultats vides)\n  if not results:\n  # On r\u00e9cup\u00e8re les informations de `Leave Application` sans la table `Leave Application Off`\n  query_fallback = \"\"\"\n  SELECT \n  s.leave_type,\n  NULL AS date_day_off, \n  s.from_date,\n  s.to_date,\n  0 AS total_off,\n  CASE \n  WHEN s.from_date < %(start_date)s AND s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, %(start_date)s) + 1\n  WHEN s.from_date < %(start_date)s THEN DATEDIFF(s.to_date, %(start_date)s) + 1\n  WHEN s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, s.from_date) + 1\n  ELSE DATEDIFF(s.to_date, s.from_date) + 1\n  END AS total_days,\n  CASE \n  WHEN s.from_date < %(start_date)s AND s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, %(start_date)s) + 1\n  WHEN s.from_date < %(start_date)s THEN DATEDIFF(s.to_date, %(start_date)s) + 1\n  WHEN s.to_date > %(end_date)s THEN DATEDIFF(%(end_date)s, s.from_date) + 1\n  ELSE DATEDIFF(s.to_date, s.from_date) + 1\n  END AS total_leave_days\n  FROM \n  `tabLeave Application` s\n  WHERE \n  s.employee = %(employee)s\n  AND s.docstatus = 1\n  AND s.from_date <= %(end_date)s\n  AND s.to_date >= %(start_date)s\n  AND s.leave_type = %(leave_type)s\n  \"\"\"\n  results = frappe.db.sql(query_fallback, {\n  \"employee\": empl.employee,\n  \"start_date\": start_date,\n  \"end_date\": end_date,\n  \"leave_type\": \"Mise \u00e0 pied\"\n  }, as_dict=True)\n  \n  if results :\n  \n  #frappe.msgprint(f'Nombre de Jour est de {results[0].total_leave_days}')\n  #doc.custom_jours_mise_a_pied = results[0].total_leave_days\n  pay_a3 = results[0].total_leave_days\n  \n  query = \"\"\"\n  SELECT \n  *\n  FROM `tabPay Leave Taken` s\n  WHERE s.parent = %s AND leave_type = 'Mise \u00e0 pied' LIMIT 1;\n  \"\"\"\n  \n  # Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres\n  results_two = frappe.db.sql(query, (doc.name), as_dict=True) \n  \n  #doc.total_leaves = 0 \n  \n  if attendance_results:\n  pay_a2 = 0\n  pay_a1 = attendance_results[0].resultats\n  employee = attendance_results[0].employee\n  \n  if Heures_results:\n  pay_a2 = Heures_results[0].nombre\n  \n  # Si des absences sont trouv\u00e9es\n  if (pay_a1 and int(pay_a1) > 0) or (pay_a2 and int(pay_a2) > 0) or (pay_a2 and int(pay_a3) > 0) :\n  # V\u00e9rification si l'employ\u00e9 existe d\u00e9j\u00e0 pour la p\u00e9riode s\u00e9lectionn\u00e9e\n  query = \"\"\"\n  SELECT * FROM `tabPay Attendance List` A\n  INNER JOIN `tabPay Attendance Line` L ON L.parent = A.name\n  WHERE L.employee = %s AND A.pay_period = %s AND A.docstatus = 1\n  \"\"\"\n  existing_records = frappe.db.sql(query, (empl.employee, doc.pay_period), as_dict=True)\n  \n  if not existing_records:\n  # Ajouter une nouvelle ligne d'pay_absence si l'enregistrement n'existe pas\n  child_doc = frappe.new_doc(\"Attendance Line\")\n  child_doc.update({\n  \"pay_absence\": pay_a1,\n  \"pay_sunday_hours\": pay_a2,\n  \"pay_custom_mise_a_pied\": pay_a3,\n  \"employee\": empl.employee\n  })\n  \n  # Ajouter \u00e0 la table parente\n  doc.append(\"attendance_line\", child_doc)\n  \n  # Marquer le document comme trouv\u00e9\n  doc.pay_find = 1\n "
        exec(script, {"self": self, "frappe": frappe, "doc": self})

        # --- from script: Before Valide Synchronise ---
        if self.pay_find == 0 :

            pay_a1 = 0
            pay_a2 = 0
            pay_a3 = 0
            pay_a4 = 0
            pay_a5 = 0
            pay_a6 = 0
            pay_a7 = 0
            pay_a8 = 0
            pay_a9 = 0
            pay_n1 = 0
            pay_n2 = 0
            pay_n3 = 0
            pay_a10 = 0
            sm = 0
            #pay_absence = 0

            All_Value = 0

            query = """
            SELECT *
            FROM `tabEmployee`
            """

            # Exécuter la requête SQL avec les paramètres
            results = frappe.db.sql(query, as_dict=True)

            for empl in results :


                query = """
                SELECT *
                FROM `tabShift Type`
                """

                # Exécuter la requête SQL avec les paramètres
                results = frappe.db.sql(query, as_dict=True)

                for Shift in results :

                    query = """

                        SELECT COUNT(*) AS resultats
                        FROM `tabAttendance` 
                        WHERE shift = %s
                        AND employee = %s
                        AND docstatus = 1
                        AND attendance_date BETWEEN %s AND %s

                        """

                    # Exécuter la requête SQL avec les paramètres
                    results = frappe.db.sql(query, (Shift.name,empl.employee, self.start_date, self.end_date), as_dict=True)


                    if results:
                        # Accéder à la pay_sum des jours de congé à partir du premier et unique enregistrement de la liste

                        if Shift.name == 'A1' :
                            pay_a1 = results[0].resultats
                        if Shift.name == 'A2' :
                            pay_a2 = results[0].resultats
                        if Shift.name == 'A3' :
                            pay_a3 = results[0].resultats
                        if Shift.name == 'A4' :
                            pay_a4 = results[0].resultats
                        if Shift.name == 'A5' :
                            pay_a5 = results[0].resultats
                        if Shift.name == 'A6' :
                            pay_a6 = results[0].resultats
                        if Shift.name == 'A7' :
                            pay_a7 = results[0].resultats
                        if Shift.name == 'A8' :
                            pay_a8 = results[0].resultats
                        if Shift.name == 'A9' :
                            pay_a9 = results[0].resultats
                        if Shift.name == 'N1' :
                            pay_n1 = results[0].resultats
                        if Shift.name == 'N2' :
                            pay_n2 = results[0].resultats
                        if Shift.name == 'N3' :
                            pay_n3 = results[0].resultats
                        if Shift.name == 'A10' :
                            pay_a10 = results[0].resultats
                        if Shift.name == 'SM' :
                            sm = results[0].resultats
                        #if Shift.name == 'O' :
                        #if Shift.name == 'O' :
                        #    pay_absence = results[0].resultats


                All_Value = pay_a1 + pay_a2 + pay_a3 + pay_a4 + pay_a5 + pay_a6 + pay_a7 + pay_a8 + pay_a9 + pay_n1 + pay_n2 + pay_n3 + pay_a10 + sm

                query = """
                    SELECT * FROM `tabPay Attendance List` A
                    INNER JOIN `tabPay Attendance Line` L on L.parent = A.name
                    WHERE L.employee = %s  AND A.pay_period = %s AND A.docstatus = 1
                """

                # Exécuter la requête SQL avec les paramètres
                results = frappe.db.sql(query, (empl.employee, self.pay_period), as_dict=True)
                #frappe.msgprint(f"Le Matricule {All_Value} se trouve déjà pour la période selectionnée") 
                #frappe.msgprint(f"Le Shift {sm} se trouve déjà pour la période selectionnée")
                if results:
                    All_Value = 0
                    All_Value = pay_a1 + pay_a2 + pay_a3 + pay_a4 + pay_a5 + pay_a6 + pay_a7 + pay_a8 + pay_a9 + pay_n1 + pay_n2 + pay_n3 + pay_a10 + sm
                    #frappe.msgprint(f"Le Matricule {empl.employee} se trouve déjà pour la période selectionnée")
                   #frappe.throw(f"Le Matricule {empl.employee} se trouve déjà pour la période selectionnée")
                    #frappe.msgprint(f"Element est pay_seniority : {All_Value} ")   
                else :
                    # Récupérer le document parent existant
                    #parent_doc = frappe.get_doc("Pay Attendance List", self.name)
                    if All_Value != 0 :
                        # Créer un nouvel enregistrement dans la table fille
                        child_doc = frappe.new_doc("Pay Attendance Line")

                        # Définir les valeurs des champs pour le nouvel enregistrement
                        child_doc.update({
                            "pay_a1" : pay_a1,
                            "pay_a2" : pay_a2,
                            "pay_a3" : pay_a3,
                            "pay_a4" : pay_a4,
                            "pay_a5" : pay_a5,
                            "pay_a6" : pay_a6,
                            "pay_a7" : pay_a7,
                            "pay_a8" : pay_a8,
                            "pay_a9" : pay_a9,
                            "pay_n1" : pay_n1,
                            "pay_n2" : pay_n2,
                            "pay_n3" : pay_n3,
                            "pay_a10" : pay_a10,
                            "pay_custom_sm" : sm,
                            "employee" : empl.employee
                        })

                        # Ajouter le nouvel enregistrement à la table parente
                        self.append("attendance_line", child_doc)
                        self.pay_find = 1
                       # parent_doc.save()


