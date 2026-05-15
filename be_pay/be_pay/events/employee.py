import frappe

def before_save(doc, method=None):
    # --- from script: Upercase ---
    if doc.first_name:
        doc.first_name = doc.first_name.upper()

    if doc.middle_name:
        doc.middle_name = doc.middle_name.upper()

    if doc.last_name:
        doc.last_name = doc.last_name.upper()

    if doc.employee_name:
        doc.employee_name = doc.employee_name.upper()


    doc.custom_cost_center_description = doc.payroll_cost_center




    date_embauche = frappe.utils.getdate(doc.date_of_joining)

    date_embauche_days = date_embauche.days
    date_embauche_month = date_embauche.month
    date_embauche_year = date_embauche.year

    start_date = frappe.utils.getdate('2025-05-21')



    #doc.custom_days_start = (date_embauche - start_date).days - 1

    # --- from script: Save categorie employe (exec fallback) ---
    script = "if(doc.status == \"Active\"):\n  \n  # V\u00e9rification initiale des champs requis\n  required_fields = ['date_of_joining', 'date_embauche', 'contract_end_date', 'salaire_de_base']\n  for field in required_fields:\n  if not doc.get(field):\n  frappe.throw(f\"Le champ {field} est requis pour le calcul\")\n  \n  date_time_string = frappe.utils.now()\n  \n  date_entree = frappe.utils.getdate(doc.date_of_joining)\n  if doc.depart == 1 :\n  if doc.relieving_date :\n  date_actuelle = frappe.utils.getdate(doc.relieving_date)\n  else :\n  frappe.throw(\"Pri\u00e8re de renseigner la date de d\u00e9part !!!\")\n  else :\n  date_actuelle = frappe.utils.getdate(date_time_string)\n  \n  date_actuelle_end = frappe.utils.getdate(doc.contract_end_date)\n  date_entree_end = frappe.utils.getdate(doc.date_embauche)\n  \n  # Initialisation des variables\n  anciennete = 0\n  years = 0\n  months = 0\n  days = 0\n  mois_actuelle = 0\n  mois_entree = 0\n  jour_entree = 0\n  jour_actuelle = 0\n  \n  # Calcul de l'anciennet\u00e9\n  if date_entree and date_actuelle:\n  anciennete = date_actuelle.year - date_entree.year\n  jour_entree = date_entree_end.day\n  mois_entree = date_entree_end.month\n  jour_actuelle = date_actuelle_end.day\n  mois_actuelle = date_actuelle_end.month\n  \n  if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):\n  anciennete = anciennete - 1\n \n  doc.anciennete = anciennete\n  \n  # Calcul des ann\u00e9es, mois et jours\n  if date_entree_end and date_actuelle_end:\n  years = date_actuelle_end.year - date_entree_end.year\n  \n  months = date_actuelle_end.month - date_entree_end.month\n  if date_actuelle_end.day < date_entree_end.day:\n  months = months - 1\n  if months < 0:\n  months = months + 12\n  years = years - 1\n  \n  # Calcul des jours\n  if date_actuelle_end.day >= date_entree_end.day:\n  days = date_actuelle_end.day - date_entree_end.day\n  else:\n  previous_month = (date_actuelle_end.month - 1) if date_actuelle_end.month > 1 else 12\n  previous_year = date_actuelle_end.year if date_actuelle_end.month > 1 else date_actuelle_end.year - 1\n  days_in_previous_month = (frappe.utils.getdate(f\"{previous_year}-{previous_month + 1}-01\") - frappe.utils.getdate(f\"{previous_year}-{previous_month}-01\")).days\n  days = (date_actuelle_end.day + int(days_in_previous_month)) - date_entree_end.day\n  \n  doc.anciennete_contract_end = years\n  \n  # Calcul du cong\u00e9 compensatoire\n  if months is not None and days is not None:\n  if days == 0:\n  doc.conge_compensatoire = months * 1.5\n  else:\n  doc.conge_compensatoire = (months + 1) * 1.5\n  else:\n  doc.conge_compensatoire = 0\n  \n  # Calcul de la gratification 13\u00e8me mois\n  if mois_actuelle is not None:\n  if days == 0:\n  doc.gratification13\u00e8_mois = ((mois_actuelle - 1) * 26) / 12\n  else:\n  doc.gratification13\u00e8_mois = (mois_actuelle * 26) / 12\n  else:\n  doc.gratification13\u00e8_mois = 0\n  \n  # S\u00e9curisation du salaire de base\n  salaire_base = (doc.salaire_de_base or 0) / 26\n  salaire_moyen = salaire_base\n  \n  # Requ\u00eate SQL\n  req = \"\"\"\n  SELECT *\n  FROM `tabEmployee Category Details`\n  WHERE %(salaire_moyen)s BETWEEN `min` AND `max`\n  \"\"\"\n  \n  categ = frappe.db.sql(\n  req,\n  {\"salaire_moyen\": salaire_moyen},\n  as_dict=True\n  )\n  \n  # Traitement du r\u00e9sultat\n  if categ:\n  for cat in categ:\n  frappe.log_error(\n  message=f\"Min: {cat.min} | Max: {cat.max}\",\n  title=f\"Cat\u00e9gorie trouv\u00e9e : {cat.description_cat\u00e9gorie}\"\n  )\n  \n  doc.employee_category_details = cat.name\n  doc.min = cat.min\n  doc.max = cat.max\n  doc.basic_salary_per_day = salaire_moyen\n  doc.description_cat\u00e9gorie = cat.description_cat\u00e9gorie_\n  doc.categories = cat.categories\n  doc.salaire_minimum_de_base = cat.basic_salary_per_day\n  \n  else:\n  frappe.throw(\n  f\"Aucune cat\u00e9gorie trouv\u00e9e pour le salaire journalier : {salaire_moyen}\"\n  )\n \n  # Initialisation des variables pour le pr\u00e9avis\n  preavis_days = 0\n  doc.preavis_days = 0 , Initialisation importante !\n  \n  # Calcul du pr\u00e9avis\n  if years is not None and doc.categories:\n  categories_basses = [\"MAN\u0152UVRE\", \"SEMI-QUALIFIE\", \"HAUTEMENT QUALIFIE\"]\n  categories_cadres = [\"CADRE DE COLLABORATION\", \"CADRE DE DIRECTION\"]\n  \n  if doc.categories in categories_basses:\n  if doc.preavis_days_manuel != 1:\n  preavis_days = 7 * years\n  doc.preavis_days = (preavis_days + 14) / 2\n  else:\n  doc.preavis_days = 0\n  \n  elif doc.categories == \"AGENT DE MAITRISE\":\n  if doc.preavis_days_manuel != 1:\n  preavis_days = 9 * years\n  doc.preavis_days = (preavis_days + 26) / 2\n  else:\n  doc.preavis_days = 0\n  \n  elif doc.categories in categories_cadres:\n  if doc.preavis_days_manuel != 1:\n  preavis_days = 16 * years\n  doc.preavis_days = (preavis_days + 78) / 2\n  else:\n  doc.preavis_days = 0\n  else:\n  doc.preavis_days_manuel = 1\n  doc.preavis_days = 0\n  else:\n  doc.preavis_days = 0\n  \n  # Calcul final avec v\u00e9rification\n  if doc.preavis_days is not None:\n  doc.conge__sur_pr\u00e9avis = (doc.preavis_days * 26) / (26 * 12)\n  else:\n  doc.conge__sur_pr\u00e9avis = 0"
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

    # --- from script: Salaire categorie employé ---
    employee_doc = frappe.get_doc('Employee Category Details', doc.employee_category_details)

    doc.basic_salary_per_day = employee_doc.pay_basic_salary_per_day

    # --- from script: Validation Employé Pourcentage Analytique 2 Activé ---
    total = 0
    #frappe.throw(str(doc.custom_analytiques[1].pourcentage))
    for row in doc.custom_analytiques:
        total = total + row.pourcentage

    if total != 100:
        frappe.throw("Le pourcentage des analytiques doit être égal 100 !!!!")


    # --- from script: anc try ---
    if(doc.status == "Active"):

        date_time_string = frappe.utils.now()

        date_entree = frappe.utils.getdate(doc.date_of_joining)
        date_actuelle = frappe.utils.getdate(date_time_string)

        # Calculate the difference in years
        anciennete = date_actuelle.year - date_entree.year

        # Adjust the years of service based on the month and day
        if date_actuelle.month < date_entree.month or (date_actuelle.month == date_entree.month and date_actuelle.day < date_entree.day):
            doc.anciennete = anciennete - 1


    # --- from script: Employe Validation Pourcentage Analytique 2 ---
    total = 0
    #frappe.throw(str(doc.custom_analytiques[1].pourcentage))
    for row in doc.custom_analytiques:
        total = total + row.pourcentage

    if total != 100:
        frappe.throw("Le pourcentage des analytiques doit être égal 100 !!!!")


def before_insert(doc, method=None):
    # --- from script: Employe Validation Pourcentage Analytique Activé ---
    total = 0
    #frappe.throw(str(doc.custom_analytiques[1].pourcentage))
    for row in doc.custom_analytiques:
        total = total + row.pourcentage

    if total != 100:
        frappe.throw("Le pourcentage des analytiques doit être égal 100 !!!!")


    # --- from script: Employe Validation Pourcentage Analytique Enabled ---
    total = 0
    #frappe.throw(str(doc.custom_analytiques[1].pourcentage))
    for row in doc.custom_analytiques:
        total = total + row.pourcentage

    if total != 100:
        frappe.throw("Le pourcentage des analytiques doit être égal 100 !!!!")

