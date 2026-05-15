import frappe

def before_save(doc, method=None):
    # --- from script: Get Mise a pied (exec fallback) ---
    script = "employee_doc = frappe.get_doc('Employee', doc.employee)\n date_time_string = frappe.utils.now()\n start_date = frappe.utils.getdate(doc.start_date)\n end_date = frappe.utils.getdate(doc.end_date)\n save = 0\n \n #frappe.msgprint(f\"\u00c9tape 1: Initialisation des dates. Date de d\u00e9but: {start_date}, Date de fin: {end_date}\")\n \n query = \"\"\"\n  SELECT\n  s.leave_type,\n  s.from_date,\n  s.to_date,\n  COUNT(f.date_day_off) AS total_off,\n  (DATEDIFF(\n  LEAST(s.to_date, %(end_date)s),\n  GREATEST(s.from_date, %(start_date)s)\n  ) + 1) AS total_days_in_period\n  FROM\n  `tabLeave Application` s\n  LEFT JOIN\n  `tabLeave Application Off` f\n  ON s.name = f.parent AND f.date_day_off BETWEEN %(start_date)s AND %(end_date)s\n  WHERE\n  s.employee = %(employee)s\n  AND s.docstatus = 1\n  AND s.from_date <= %(end_date)s\n  AND s.to_date >= %(start_date)s\n  AND s.leave_type = %(leave_type)s\n  GROUP BY\n  s.name\n \"\"\"\n results = frappe.db.sql(query, {\n  \"employee\": doc.employee,\n  \"start_date\": start_date,\n  \"end_date\": end_date,\n  \"leave_type\": \"Mise \u00e0 pied\"\n }, as_dict=True)\n \n #frappe.msgprint(f\"\u00c9tape 2: Ex\u00e9cution de la premi\u00e8re requ\u00eate. Nombre de r\u00e9sultats: {len(results)}\")\n \n if results:\n  result = results[0]\n  #frappe.msgprint(f\"\u00c9tape 3: R\u00e9sultats de la requ\u00eate trouv\u00e9s. total_days_in_period: {result.total_days_in_period}, total_off: {result.total_off}\")\n  total_leave_days = result.total_days_in_period - result.total_off\n  doc.custom_jours_mise_a_pied = total_leave_days\n  #frappe.msgprint(f\"\u00c9tape 4: Calcul final. Nombre de jours de mise \u00e0 pied: {total_leave_days}\")\n else:\n  doc.custom_jours_mise_a_pied = 0\n  #frappe.msgprint(\"\u00c9tape 3 (alternative): Aucun r\u00e9sultat trouv\u00e9 pour la premi\u00e8re requ\u00eate. Jours de mise \u00e0 pied mis \u00e0 0.\")\n \n query_two = \"\"\"\n  SELECT\n  *\n  FROM `tabLeave Taken` s\n  WHERE s.parent = %s AND leave_type = 'Mise \u00e0 pied' LIMIT 1;\n \"\"\"\n results_two = frappe.db.sql(query_two, (doc.name), as_dict=True)\n \n #frappe.msgprint(f\"\u00c9tape 5: Ex\u00e9cution de la deuxi\u00e8me requ\u00eate. Nombre de r\u00e9sultats: {len(results_two)}\")"
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Attendance get list Sauv ---
    query = """
       SELECT
            s.hours_30,
            s.hours_60,
            s.sunday_hours,
            s.custom_mise_a_pied,
            s.absence,
            s.custom_presence
        FROM
            `tabAttendance Line` s
        INNER JOIN
            `tabAttendance List` d ON d.name = s.parent
        WHERE
            d.pay_period = %s
            AND
            s.employee = %s
            AND
            s.docstatus = 1
    """

    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True)

    Renvoie = 0

    if results : 

        doc.custom_heure_suplementaire = results[0].sunday_hours
        doc.custom_absences = results[0].absence
        doc.custom_jours_mise_a_pied = results[0].custom_mise_a_pied
        doc.custom_presence = results[0].custom_presence



    # --- from script: Anciennete sur fiche ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    date_time_string = frappe.utils.now()

    date_entree = frappe.utils.getdate(employee_doc.date_of_joining)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.anciennete = anciennete
    employee_doc.anciennete = anciennete
    employee_doc.save()

    # --- from script: Get Decompte Final ---
    decompte_list = frappe.db.sql(
        """
        SELECT *
        FROM `tabFinal Settlement`
        WHERE employee = %s
          AND date_fin_contrat BETWEEN %s AND %s
          AND docstatus = 1
        """,
        (doc.employee, doc.start_date, doc.end_date),
        as_dict=True
    )

    if decompte_list:
        doc.custom_total_days = decompte_list[0].total_jours
        doc.custom_jour_preste = decompte_list[0].jour_preste
    else :
        doc.custom_total_days = 0
        doc.custom_jour_preste = 0

    # --- from script: Get Leave Provision ---
        #doc.save() # Sauvegarde le document principal, ce qui commit les changements.
    #projet_val = doc.end_date[:4]
    projet_val = frappe.utils.getdate(doc.end_date).year if doc.end_date else ""
    Period = frappe.get_all("Pay Provision", filters={"fiscal_year": projet_val, "employment_type":doc.employment_type}, fields=["name","start_date","end_date"], limit=1)

    start_date = ""
    end_date = ""
    names = ""

    if Period :

        start_date = Period[0].start_date 
        end_date = Period[0].end_date 
        names = Period[0].name 

    doc.from_date = start_date
    doc.to_date = end_date

    conge_list = frappe.db.sql(
    				"""
    				SELECT * 
    				FROM `tabProvision Ratio`
    				WHERE employee = %s AND parent = %s
    				""", (doc.employee, names), as_dict=1
    			)
    if conge_list :

        doc.leave_allouer = int(conge_list[0].pris) + int(conge_list[0].total) - int(conge_list[0].report)
        doc.pris = conge_list[0].pris
        doc.reste_a_prendre = conge_list[0].total
        doc.custom_repport = conge_list[0].report

    # --- from script: Get Avance Salaire ---
    QUERY = frappe.db.sql(
    		""" 
    		SELECT MAX(incentive_amount) AS Amount from `tabEmployee Incentive` 
    		WHERE docstatus = 1 AND salary_component = 'Salary Advance' AND employee = %s 
    		AND payroll_date BETWEEN %s AND %s
    		""",
    		(doc.employee,doc.start_date, doc.end_date),
    	)

    doc.custom_total_avance = QUERY.Amount


    # --- from script: Valide Salary Cach ---
    query = """
       SELECT
         *
        FROM
            `tabEmployee`
        WHERE
            employee = %s
    """

    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (doc.employee), as_dict=True)

    if results :
        #frappe.msgprint(f' Find {results[0].local_bank}')
        if doc.custom_get_local_bank == 1 :
            log(f' Find {results[0].local_bank}')
        else :
            doc.bank = results[0].local_bank

    if doc.net_pay:

        doc.autres = float(doc.net_pay)
        if doc.cash is not None and doc.bank is not None:
            doc.autres = float(doc.net_pay) - float(doc.cash) - float(doc.bank)

        elif doc.cash is not None:
            doc.autres = float(doc.net_pay) - float(doc.cash)

        elif doc.bank is not None and doc.bank != 0  :
            #doc.autres = float(doc.net_pay) - float(doc.bank)
            doc.autres = 0
            #frappe.msgprint(f' Find {results[0].local_bank}')
        else:
            doc.autres = float(doc.net_pay)

    #doc.autres = 20

    # --- from script: Leave Accorder (exec fallback) ---
    script = "# R\u00e9cup\u00e9rer le document de l'employ\u00e9\n employee_doc = frappe.get_doc('Employee', doc.employee)\n \n # Obtenir la date et l'heure actuelles\n date_time_string = frappe.utils.now()\n \n # Convertir les dates de d\u00e9but et de fin en objets date\n start_date = frappe.utils.getdate(doc.start_date)\n end_date = frappe.utils.getdate(doc.end_date)\n \n # Initialiser une variable pour v\u00e9rifier si des modifications ont \u00e9t\u00e9 enregistr\u00e9es\n save = 0\n \n # Requ\u00eate SQL pour r\u00e9cup\u00e9rer les jours de cong\u00e9 pris par type de cong\u00e9\n query = \"\"\"\n SELECT\n  s.leave_type,\n  SUM(\n  DATEDIFF(\n  LEAST(s.to_date, %(end_date)s),\n  GREATEST(s.from_date, %(start_date)s)\n  ) + 1\n  ) AS total_leave_days\n FROM `tabLeave Application` s\n WHERE s.employee = %(employee)s\n  AND s.docstatus = 1\n  AND (\n  (s.from_date <= %(end_date)s AND s.to_date >= %(start_date)s) -- Chevauchement partiel ou total\n  )\n GROUP BY s.leave_type;\n \"\"\"\n \n # Param\u00e8tres pour la requ\u00eate SQL\n params = {\n  \"employee\": doc.employee, , Assurez-vous que doc.employee est correctement d\u00e9fini\n  \"start_date\": start_date, , Assurez-vous que start_date est au format 'YYYY-MM-DD'\n  \"end_date\": end_date , Assurez-vous que end_date est au format 'YYYY-MM-DD'\n }\n \n # Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres\n results = frappe.db.sql(query, params, as_dict=True)\n \n # V\u00e9rifier si des r\u00e9sultats ont \u00e9t\u00e9 retourn\u00e9s\n for send in results:\n \n  # Forcer un maximum de 26 jours\n  total_days = send.total_leave_days\n  if total_days > 26:\n  total_days = 26\n \n  # V\u00e9rifier si le type de cong\u00e9 existe d\u00e9j\u00e0\n  query_two = \"\"\"\n  SELECT\n  name\n  FROM `tabSalary Slip Taken`\n  WHERE parent = %s AND leave_type = %s LIMIT 1;\n  \"\"\"\n \n  results_two = frappe.db.sql(query_two, (doc.name, send.leave_type), as_dict=True)\n \n  if results_two:\n  save = 1\n \n  # Mise \u00e0 jour du jour avec limite appliqu\u00e9e\n  frappe.db.set_value('Salary Slip Taken', results_two[0].name, 'jour', total_days)\n \n  doc_conge = frappe.get_doc('Salary Slip Taken', results_two[0].name)\n  doc_conge.db_set('jour', total_days, commit=True)\n \n  else:\n  # Ajouter une nouvelle entr\u00e9e dans \"Leave Taken\"\n  doc.append(\"custom_salary_slip_pris\", {\n  \"leave_type\": send.get('leave_type'),\n  \"jour\": total_days,\n  \"fraction\": 0\n  })\n "
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Anciennete Day ---

    # Définition des dates de début et de fin
    #date_debut = frappe.utils.getdate('16/10/2013', '%d/%m/%Y')
    #date_fin = frappe.utils.getdate('20/12/2024', '%d/%m/%Y')
    date_debut = frappe.utils.getdate(doc.date_embauche)
    date_fin = frappe.utils.getdate(doc.to_date)
    # Calcul de la différence en mois
    difference_mois = (date_fin.year - date_debut.year) * 12 + date_fin.month - date_debut.month

    doc.anciennete_day = difference_mois / 12

    # --- from script: Recuperation Antendance List ---
    query = """
          SELECT
            s.absence,
            s.employee,
            s.a1,
            s.a2,
            s.a3,
            s.a4,
            s.a5,
            s.a6,
            s.a7,
            s.a8,
            s.a9,
            s.n1,
            s.n2,
            s.n3,
            s.custom_sm
        FROM
            `tabAttendance Line` s
        INNER JOIN
            `tabAttendance List` d ON d.name = s.parent
        WHERE
            d.pay_period = %s
            AND
            s.employee = %s
            AND
            s.docstatus = 1
    """

    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True)
    #frappe.msgprint(f'Valeur Renvoyé Periode {doc.pay_period}')
    Renvoie = 0

    if results : 
        doc.custom_abscences = results[0].absence
        doc.custom_sm = results[0].custom_sm
        doc.a1 = results[0].a1
        Renvoie = Renvoie + ( results[0].a1 * 1)
        doc.a2 = results[0].a2
        Renvoie = Renvoie + ( results[0].a2 * 2)
        doc.a3 = results[0].a3
        Renvoie = Renvoie + ( results[0].a3 * 2)
        doc.a4 = results[0].a4
        Renvoie = Renvoie + ( results[0].a4 * 3)
        doc.a5 = results[0].a5
        Renvoie = Renvoie + ( results[0].a5 * 3.3)
        doc.a6 = results[0].a6
        Renvoie = Renvoie + ( results[0].a6 * 4)
        doc.a7 = results[0].a7
        Renvoie = Renvoie + ( results[0].a7 * 5)
        doc.a8 = results[0].a8
        Renvoie = Renvoie + ( results[0].a8 * 6)
        doc.a9 = results[0].a9
        Renvoie = Renvoie + ( results[0].a9 * 10)
        doc.n1 = results[0].n1
        Renvoie = Renvoie + ( results[0].n1 * 7)
        doc.n2 = results[0].n2
        Renvoie = Renvoie + ( results[0].n2 * 6.3)
        doc.n3 = results[0].n3
        Renvoie = Renvoie + ( results[0].n3 * 7)

    doc.night_hours = Renvoie
    #frappe.msgprint(f'Valeur Renvoyé {Renvoie}')

    query = """
        SELECT
            total_leaves_allocated
        FROM
            `tabLeave Allocation` s
        WHERE
            from_date = %s
        AND
            to_date = %s
        AND
            employee = %s
    """
    start_date = frappe.utils.getdate(doc.start_date)
    end_date = frappe.utils.getdate(doc.end_date)
    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (start_date,end_date, doc.employee), as_dict=True)




    # --- from script: Recuperation Attendance List (exec fallback) ---
    script = "query = \"\"\" SELECT s.hours_30, s.hours_60, s.sunday_hours, s.absence FROM `tabAttendance Line` s INNER JOIN `tabAttendance List` d ON d.name = s.parent WHERE d.pay_period = %s AND s.employee = %s AND s.docstatus = 1 \"\"\" , Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True) Renvoie = 0 if results : doc.custom_h30 = results[0].hours_30 doc.custom_h60 = results[0].hours_60 doc.custom_h100 = results[0].sunday_hours doc.custom_absences = results[0].absence if frappe.utils.getdate(doc.end_date).month == 12 : ValSave = 0 ValResev = 0 DateIn = 0 DateEnd = 0 jour = 0 Day_find = 0 if frappe.utils.getdate(doc.custom_scheduled_confirmation_date) < frappe.utils.getdate(f\"{frappe.utils.getdate(doc.end_date).year}\" + \"-01-01\") : ValResev = 12 else : , R\u00e9cup\u00e9rer les dates start_date = frappe.utils.getdate(doc.custom_scheduled_confirmation_date) end_date = frappe.utils.getdate(doc.end_date) , Calcul du nombre de mois ValResev = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) , Gestion des jours partiels if start_date.day > 15 : ValResev = ValResev + 0 else : ValResev = ValResev + 1 , Affichez le r\u00e9sultat #frappe.msgprint(f\"Le nombre de mois entre les deux dates est : {start_date.day} === {ValResev}\") doc.custom_nombre_mois_annuel = ValResev "
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Assignement new salary categorie for depart before save ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    if employee_doc.custom_depart == 1 :
        if (employee_doc.employee_category_details == "1A" or employee_doc.employee_category_details == "1B" or employee_doc.employee_category_details == "2") :
            doc.custom_salaire_categorise_au_depart = employee_doc.pay_basic_salary_per_day;
            doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day;
            #frappe.msgprint('Message ' + frm.doc.basic_salary_per_day)
        else :
            doc.custom_salaire_categorise_au_depart = employee_doc.pay_basic_salary_per_day
            doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day;
    else :
            doc.custom_salaire_categorise_au_depart = employee_doc.pay_basic_salary_per_day;
            doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day;


    # --- from script: Save anciennete fiche avant sauv ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    date_time_string = frappe.utils.now()

    date_entree = frappe.utils.getdate(employee_doc.date_of_joining)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.anciennete = anciennete
    employee_doc.anciennete = anciennete

    date_entree = frappe.utils.getdate(employee_doc.scheduled_confirmation_date)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.custom_anciennete_fin_prestation = anciennete
    employee_doc.custom_ancienneté_fin_préstation = anciennete
    employee_doc.save()


def before_insert(doc, method=None):
    # --- from script: Attendance get list ---
    query = """
       SELECT
            s.hours_30,
            s.hours_60,
            s.sunday_hours,
            s.custom_mise_a_pied,
            s.absence,
            s.custom_presence
        FROM
            `tabAttendance Line` s
        INNER JOIN
            `tabAttendance List` d ON d.name = s.parent
        WHERE
            d.pay_period = %s
            AND
            s.employee = %s
            AND
            s.docstatus = 1
    """

    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True)

    Renvoie = 0

    if results : 

        doc.custom_heure_suplementaire = results[0].sunday_hours
        doc.custom_absences = results[0].absence
        doc.custom_jours_mise_a_pied = results[0].custom_mise_a_pied
        doc.custom_presence = results[0].custom_presence



    # --- from script: Accord Leave Save (exec fallback) ---
    script = "# R\u00e9cup\u00e9rer le document de l'employ\u00e9\n employee_doc = frappe.get_doc('Employee', doc.employee)\n \n # Obtenir la date et l'heure actuelles\n date_time_string = frappe.utils.now()\n \n # Convertir les dates de d\u00e9but et de fin en objets date\n start_date = frappe.utils.getdate(doc.start_date)\n end_date = frappe.utils.getdate(doc.end_date)\n \n # Initialiser une variable pour v\u00e9rifier si des modifications ont \u00e9t\u00e9 enregistr\u00e9es\n save = 0\n \n # Requ\u00eate SQL pour r\u00e9cup\u00e9rer les jours de cong\u00e9 pris par type de cong\u00e9\n query = \"\"\"\n SELECT\n  s.leave_type,\n  SUM(\n  DATEDIFF(\n  LEAST(s.to_date, %(end_date)s),\n  GREATEST(s.from_date, %(start_date)s)\n  ) + 1\n  ) AS total_leave_days\n FROM `tabLeave Application` s\n WHERE s.employee = %(employee)s\n  AND s.docstatus = 1\n  AND (\n  (s.from_date <= %(end_date)s AND s.to_date >= %(start_date)s) -- Chevauchement partiel ou total\n  )\n GROUP BY s.leave_type;\n \"\"\"\n \n # Param\u00e8tres pour la requ\u00eate SQL\n params = {\n  \"employee\": doc.employee, , Assurez-vous que doc.employee est correctement d\u00e9fini\n  \"start_date\": start_date, , Assurez-vous que start_date est au format 'YYYY-MM-DD'\n  \"end_date\": end_date , Assurez-vous que end_date est au format 'YYYY-MM-DD'\n }\n \n # Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres\n results = frappe.db.sql(query, params, as_dict=True)\n \n # V\u00e9rifier si des r\u00e9sultats ont \u00e9t\u00e9 retourn\u00e9s\n if results:\n  \n  for send in results:\n  # Requ\u00eate SQL pour v\u00e9rifier si le type de cong\u00e9 existe d\u00e9j\u00e0 dans \"Leave Taken\"\n  query_two = \"\"\"\n  SELECT\n  name\n  FROM `tabSalary Slip Taken`\n  WHERE parent = %s AND leave_type = %s LIMIT 1;\n  \"\"\"\n \n  # Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres\n  results_two = frappe.db.sql(query_two, (doc.name, send.leave_type), as_dict=True)\n \n  # Si le type de cong\u00e9 existe d\u00e9j\u00e0, mettre \u00e0 jour le nombre de jours\n  if results_two and len(results_two) > 0: , V\u00e9rifier que results_two n'est pas vide\n  save = 1\n  frappe.db.set_value('Salary Slip Taken', results_two[0].name, 'jour', send.total_leave_days)\n  \n  # R\u00e9initialiser le statut du document pour permettre la mise \u00e0 jour\n  doc_conge = frappe.get_doc('Salary Slip Taken', results_two[0].name)\n  doc_conge.db_set('jour', send.total_leave_days, commit=True)\n  \n  # Valider les modifications\n  #frappe.db.commit()\n  #frappe.msgprint(f'Trouv\u00e9 encore {send.get(\"leave_type\")}')\n  else:\n  # Ajouter une nouvelle entr\u00e9e dans \"Leave Taken\"\n  doc.append(\"custom_salary_slip_pris\", {\n  \"leave_type\": send.get('leave_type'),\n  \"jour\": send.get('total_leave_days'),\n  \"fraction\": 0\n  })\n \n "
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Recuperation Antendance List Insert ---
    query = """
       SELECT
            s.absence,
            s.a1,
            s.a2,
            s.a3,
            s.a4,
            s.a5,
            s.a6,
            s.a7,
            s.a8,
            s.a9,
            s.n1,
            s.n2,
            s.n3
        FROM
            `tabAttendance Line` s
        INNER JOIN
            `tabAttendance List` d ON d.name = s.parent
        WHERE
            d.pay_period = %s
            AND
            s.employee = %s
            AND
            s.docstatus = 1
    """

    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True)

    Renvoie = 0

    if results : 
        doc.custom_abscences = results[0].absence
        doc.a1 = results[0].a1
        Renvoie = Renvoie + ( doc.a1 * 1)
        doc.a2 = results[0].a2
        Renvoie = Renvoie + ( doc.a2 * 2)
        doc.a3 = results[0].a3
        Renvoie = Renvoie + ( doc.a3 * 2)
        doc.a4 = results[0].a4
        Renvoie = Renvoie + ( doc.a4 * 3)
        doc.a5 = results[0].a5
        Renvoie = Renvoie + ( doc.a5 * 3.3)
        doc.a6 = results[0].a6
        Renvoie = Renvoie + ( doc.a6 * 4)
        doc.a7 = results[0].a7
        Renvoie = Renvoie + ( doc.a7 * 5)
        doc.a8 = results[0].a8
        Renvoie = Renvoie + ( doc.a8 * 6)
        doc.a9 = results[0].a9
        Renvoie = Renvoie + ( doc.a9 * 10)
        doc.n1 = results[0].n1
        Renvoie = Renvoie + ( doc.n1 * 7)
        doc.n2 = results[0].n2
        Renvoie = Renvoie + ( doc.n2 * 6.3)
        doc.n3 = results[0].n3
        Renvoie = Renvoie + ( doc.n3 * 7)

    doc.night_hours = Renvoie


    query = """
        SELECT
            total_leaves_allocated
        FROM
            `tabLeave Allocation` s
        WHERE
            from_date = %s
        AND
            to_date = %s
        AND
            employee = %s
    """
    start_date = frappe.utils.getdate(doc.start_date)
    end_date = frappe.utils.getdate(doc.end_date)
    # Exécuter la requête SQL avec les paramètres
    results = frappe.db.sql(query, (start_date,end_date, doc.employee), as_dict=True)




    # --- from script: Recuperation Attendance List Insert (exec fallback) ---
    script = "query = \"\"\" SELECT s.hours_30, s.hours_60, s.sunday_hours, s.absence FROM `tabAttendance Line` s INNER JOIN `tabAttendance List` d ON d.name = s.parent WHERE d.pay_period = %s AND s.employee = %s AND s.docstatus = 1 \"\"\" , Ex\u00e9cuter la requ\u00eate SQL avec les param\u00e8tres results = frappe.db.sql(query, (doc.pay_period, doc.employee), as_dict=True) Renvoie = 0 if results : doc.custom_h30 = results[0].hours_30 doc.custom_h60 = results[0].hours_60 doc.custom_h100 = results[0].sunday_hours doc.custom_absences = results[0].absence if frappe.utils.getdate(doc.end_date).month == 12 : ValSave = 0 ValResev = 0 DateIn = 0 DateEnd = 0 jour = 0 Day_find = 0 if frappe.utils.getdate(doc.custom_scheduled_confirmation_date) < frappe.utils.getdate(f\"{frappe.utils.getdate(doc.end_date).year}\" + \"-01-01\") : ValResev = 12 else : , R\u00e9cup\u00e9rer les dates start_date = frappe.utils.getdate(doc.custom_scheduled_confirmation_date) end_date = frappe.utils.getdate(doc.end_date) , Calcul du nombre de mois ValResev = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) , Gestion des jours partiels if start_date.day > 15 : ValResev = ValResev + 0 else : ValResev = ValResev + 1 , Affichez le r\u00e9sultat #frappe.msgprint(f\"Le nombre de mois entre les deux dates est : {start_date.day} === {ValResev}\") doc.custom_nombre_mois_annuel = ValResev "
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Save anciennete fiche avant insert ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    date_time_string = frappe.utils.now()

    date_entree = frappe.utils.getdate(employee_doc.date_of_joining)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.anciennete = anciennete
    employee_doc.anciennete = anciennete

    date_entree = frappe.utils.getdate(employee_doc.scheduled_confirmation_date)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.custom_anciennete_fin_prestation = anciennete
    employee_doc.custom_ancienneté_fin_préstation = anciennete
    employee_doc.save()

    # --- from script: Save fiche anciennete ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    date_time_string = frappe.utils.now()

    date_entree = frappe.utils.getdate(employee_doc.date_of_joining)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):
        anciennete = anciennete - 1

    doc.anciennete = anciennete   
    employee_doc.anciennete = anciennete
    employee_doc.save()



def after_insert(doc, method=None):
    # --- from script: Assignement new salary categorie for depart before insert new ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    doc.custom_salaire_categorise_au_depart = employee_doc.pay_basic_salary_per_day;
    doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day;
    #frappe.msgprint('Message ' + frm.doc.basic_salary_per_day)


def before_submit(doc, method=None):
    # --- from script: Assignement new salary categorie for depart before insert ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    doc.custom_salaire_categorise_au_depart = employee_doc.pay_basic_salary_per_day;
    doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day;
    #frappe.msgprint('Message ' + frm.doc.basic_salary_per_day)


def before_validate(doc, method=None):
    # --- from script: Save anciennete fiche avant validation ---
    employee_doc = frappe.get_doc('Employee', doc.employee)

    date_time_string = frappe.utils.now()

    date_entree = frappe.utils.getdate(employee_doc.date_of_joining)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.anciennete = anciennete
    employee_doc.anciennete = anciennete

    date_entree = frappe.utils.getdate(employee_doc.scheduled_confirmation_date)
    date_actuelle = frappe.utils.getdate(date_time_string)

    # Calculate the difference in years
    anciennete = date_actuelle.year - date_entree.year

    # Adjust the years of service based on the month and day
    if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):

        anciennete = anciennete - 1

    doc.custom_anciennete_fin_prestation = anciennete
    employee_doc.custom_ancienneté_fin_préstation = anciennete
    employee_doc.save()

