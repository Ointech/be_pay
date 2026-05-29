import frappe
import requests
from datetime import datetime, timedelta
from frappe.utils import now, getdate, formatdate, add_days, now_datetime


def cron():
    """
    Point d'entrée appelé par le scheduler (toutes les heures).
    Lit la configuration Pay Attendance Retrieval Settings et enqueue
    la récupération des pointages par employé et par serveur actif.
    """
    logger = frappe.logger("attendance_retrieval")

    # ------------------------------------------------------------------
    # 1. Récupérer la configuration globale
    # ------------------------------------------------------------------
    try:
        settings = frappe.get_single("Pay Attendance Retrieval Settings")
    except Exception:
        logger.warning("Pay Attendance Retrieval Settings introuvable.")
        return

    if not settings or not getattr(settings, "pay_enabled", 0):
        logger.info("Récupération désactivée dans Pay Attendance Retrieval Settings.")
        return

    servers = getattr(settings, "pay_servers", []) or []
    if not servers:
        logger.info("Aucun serveur configuré.")
        return

    now_dt = now_datetime()
    logger.info("Démarrage cron : %s serveur(s) à traiter.", len(servers))

    # ------------------------------------------------------------------
    # 2. Itérer sur chaque serveur configuré
    # ------------------------------------------------------------------
    for server in servers:
        if not getattr(server, "pay_enabled", 0):
            continue

        url_base = (getattr(server, "pay_url_base", "") or "").strip()
        token = (getattr(server, "pay_token", "") or "").strip()
        staff = (getattr(server, "pay_staff", "") or "").strip()
        username = (getattr(server, "pay_username", "") or "").strip()
        password = (getattr(server, "pay_password", "") or "").strip()

        if not url_base or not token:
            logger.error("Serveur %s ignoré : url_base ou token manquant.", server.name)
            continue

        # ------------------------------------------------------------------
        # 3. Récupérer les employés actifs du employment_type lié au serveur
        # ------------------------------------------------------------------
        employees = frappe.get_all(
            "Employee",
            filters={
                "status": "Active",
                "employment_type": staff,
            },
            fields=["name", "employee_name", "date_of_joining", "attendance_device_id"],
        )

        if not employees:
            logger.info("Aucun employé actif pour le staff '%s'.", staff)
            continue

        logger.info(
            "Serveur %s : %s employé(s) à traiter.",
            getattr(server, "pay_server_name", server.name),
            len(employees),
        )

        # ------------------------------------------------------------------
        # 4. Enqueue un job par employé (queue long, timeout 1h)
        # ------------------------------------------------------------------
        for emp in employees:
            # L'API ZKTECO utilise attendance_device_id (ou name en fallback)
            emp_code = (emp.attendance_device_id or "").strip() or emp.name
            frappe.enqueue(
                "be_pay.tasks.cron_execute",
                url_base=url_base,
                token=token,
                username=username,
                password=password,
                employee=emp.name,
                emp_code=emp_code,
                date_of_joining=emp.date_of_joining,
                queue="long",
                timeout=3600,
            )

        # ------------------------------------------------------------------
        # 5. Mettre à jour le last_run du serveur
        # ------------------------------------------------------------------
        try:
            frappe.db.set_value(
                "Pay Attendance Retrieval Server",
                server.name,
                "pay_last_run",
                now_dt,
            )
        except Exception:
            logger.warning(
                "Impossible de mettre à jour pay_last_run pour %s",
                server.name,
                exc_info=True,
            )


def cron_execute(
    url_base=None,
    token=None,
    username=None,
    password=None,
    employee=None,
    emp_code=None,
    date_of_joining=None,
    force_date_from=None,
    force_date_to=None,
):
    """
    Récupère les pointages ZKTECO pour un employé sur une fenêtre de dates
    et crée les Employee Checkin correspondants s'ils n'existent pas déjà.

    Paramètres:
        url_base  : URL de base de l'API ZKTECO.
        token     : Token JWT d'authentification.
        username  : Nom d'utilisateur API (basic auth).
        password  : Mot de passe API (basic auth).
        employee  : ID de l'employé (matricule).
        date_of_joining : Date d'embauche (les pointages avant cette date sont ignorés).
        force_date_from : Force la date de début (format yyyy-mm-dd), sinon J-35.
        force_date_to   : Force la date de fin (format yyyy-mm-dd), sinon J+2.
    """
    logger = frappe.logger("attendance_retrieval")

    if not employee:
        logger.warning("cron_execute appelé sans employee.")
        return

    # emp_code = code employe dans ZKTECO (attendance_device_id ou name)
    emp_code = emp_code or employee

    # ------------------------------------------------------------------
    # 1. Déterminer la fenêtre de récupération
    # ------------------------------------------------------------------
    if force_date_from and force_date_to:
        date_from_str = force_date_from
        date_to_str = force_date_to
    else:
        today = now_datetime()
        date_from = add_days(today, -35)
        date_to = add_days(today, 2)
        date_from_str = formatdate(date_from, "yyyy-mm-dd")
        date_to_str = formatdate(date_to, "yyyy-mm-dd")

    # ------------------------------------------------------------------
    # 2. Préparer les headers et l'URL
    # ------------------------------------------------------------------
    headers = {
        "Authorization": f"JWT {token}",
        "Content-Type": "application/json",
    }

    page = 1
    limit = 1000
    all_records = []

    try:
        # --------------------------------------------------------------
        # 3. Pagination sur l'API (max 20 pages de sécurité)
        # --------------------------------------------------------------
        def _fetch_records(use_emp_code=True):
            """Helper : récupère les records avec ou sans filtre emp_code."""
            _page = 1
            _records = []
            while _page <= 20:
                if use_emp_code:
                    url = (
                        f"{url_base}?"
                        f"emp_code={emp_code}"
                        f"&start_time={date_from_str} 00:00:00"
                        f"&end_time={date_to_str} 00:00:00"
                        f"&limit={limit}"
                        f"&page={_page}"
                    )
                else:
                    url = (
                        f"{url_base}?"
                        f"start_time={date_from_str} 00:00:00"
                        f"&end_time={date_to_str} 00:00:00"
                        f"&limit={limit}"
                        f"&page={_page}"
                    )

                resp = requests.get(
                    url,
                    auth=(username, password) if username and password else None,
                    headers=headers,
                    timeout=60,
                )

                if resp.status_code != 200:
                    logger.error(
                        "Erreur HTTP %s pour %s (page %s, emp_code=%s)",
                        resp.status_code,
                        employee,
                        _page,
                        use_emp_code,
                    )
                    break

                payload = resp.json()
                if not isinstance(payload, dict) or "data" not in payload:
                    logger.warning("Format de réponse inattendu pour %s.", employee)
                    break

                batch = payload["data"]
                if not batch:
                    break

                _records.extend(batch)
                _page += 1
            return _records

        # Essayer d'abord avec le filtre emp_code
        all_records = _fetch_records(use_emp_code=True)

        # Fallback : si aucun record, récupérer tout et filtrer côté client
        if not all_records:
            all_records = _fetch_records(use_emp_code=False)
            all_records = [
                r for r in all_records
                if str(r.get("emp_code", "")).strip() == emp_code
            ]

        if not all_records:
            logger.info("Aucun pointage trouvé pour %s (emp_code=%s) sur la période.", employee, emp_code)
            return

        # ------------------------------------------------------------------
        # 4. Traiter chaque pointage
        # ------------------------------------------------------------------
        date_of_joining = getdate(date_of_joining) if date_of_joining else None
        created_count = 0
        skipped_count = 0

        for record in all_records:
            punch_time_str = record.get("punch_time")
            if not punch_time_str:
                continue

            punch_time = getdate(punch_time_str)

            # Ignorer les pointages antérieurs à la date d'embauche
            if date_of_joining and punch_time < date_of_joining:
                continue

            # Déterminer IN / OUT
            punch_state = record.get("punch_state_display", "")
            terminal_sn = record.get("terminal_sn", "")

            if punch_state == "Check In":
                log_type = "IN"
            elif punch_state == "Check Out":
                log_type = "OUT"
            else:
                # Fallback par terminal SN (liste des bornes d'entrée)
                in_terminals = {
                    "CGT9221060018", "BAY5240500035", "BAY5240500077",
                    "BAY5240500078", "BAY5240500099", "CGT9221060020",
                    "CGT9221060023", "BAY5244500049",
                }
                log_type = "IN" if terminal_sn in in_terminals else "OUT"

            # Vérifier si un pointage identique (même employé, même date,
            # même log_type) existe déjà pour éviter les doublons.
            punch_date_str = str(punch_time)
            exists = frappe.db.sql(
                """
                SELECT 1 FROM `tabEmployee Checkin`
                WHERE employee = %s
                  AND log_type = %s
                  AND DATE(time) = %s
                LIMIT 1
                """,
                (employee, log_type, punch_date_str),
            )

            if exists:
                skipped_count += 1
                continue

            # Créer le Employee Checkin
            checkin = frappe.new_doc("Employee Checkin")
            checkin.employee = employee
            checkin.employee_name = record.get("first_name", employee)
            checkin.time = punch_time_str
            checkin.log_type = log_type
            checkin.device_id = terminal_sn
            checkin.insert(ignore_permissions=True)
            created_count += 1

        frappe.db.commit()
        logger.info(
            "Employé %s : %s créé(s), %s ignoré(s).",
            employee,
            created_count,
            skipped_count,
        )

    except requests.exceptions.Timeout:
        logger.error("Timeout API ZKTECO pour %s.", employee)
    except requests.exceptions.ConnectionError as e:
        logger.error("Erreur de connexion ZKTECO pour %s : %s", employee, str(e))
    except Exception as e:
        logger.error(
            "Erreur inattendue cron_execute (%s) : %s", employee, str(e), exc_info=True
        )


def cron_historical(date_from="2026-04-01", date_to=None):
    """
    Lance la récupération historique des pointages ZKTECO pour TOUS les employés
    actifs depuis une date de début donnée. Par défaut depuis le 01/04/2026.
    Enqueue un job par employé (queue long) pour ne pas bloquer.
    """
    logger = frappe.logger("attendance_retrieval")

    if not date_to:
        date_to = formatdate(add_days(now_datetime(), 2), "yyyy-mm-dd")

    try:
        settings = frappe.get_single("Pay Attendance Retrieval Settings")
    except Exception:
        logger.warning("Pay Attendance Retrieval Settings introuvable.")
        return

    if not settings or not getattr(settings, "pay_enabled", 0):
        logger.info("Récupération désactivée.")
        return

    servers = getattr(settings, "pay_servers", []) or []
    if not servers:
        logger.info("Aucun serveur configuré.")
        return

    # Récupérer tous les employés actifs (tous types confondus)
    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "date_of_joining", "attendance_device_id", "employment_type"],
    )

    logger.info(
        "cron_historical : %s employés à traiter du %s au %s.",
        len(employees),
        date_from,
        date_to,
    )

    enqueued = 0
    for emp in employees:
        # Trouver le serveur correspondant à l'employment_type de l'employé
        server = None
        for srv in servers:
            if getattr(srv, "pay_staff", "") == emp.employment_type:
                server = srv
                break

        if not server:
            # Si aucun serveur spécifique, prendre le premier serveur actif
            for srv in servers:
                if getattr(srv, "pay_enabled", 0):
                    server = srv
                    break

        if not server:
            logger.warning("Aucun serveur actif pour %s.", emp.name)
            continue

        url_base = (getattr(server, "pay_url_base", "") or "").strip()
        token = (getattr(server, "pay_token", "") or "").strip()
        username = (getattr(server, "pay_username", "") or "").strip()
        password = (getattr(server, "pay_password", "") or "").strip()

        if not url_base or not token:
            logger.error("Serveur incomplet pour %s.", emp.name)
            continue

        emp_code = (emp.attendance_device_id or "").strip() or emp.name

        frappe.enqueue(
            "be_pay.tasks.cron_execute",
            url_base=url_base,
            token=token,
            username=username,
            password=password,
            employee=emp.name,
            emp_code=emp_code,
            date_of_joining=emp.date_of_joining,
            force_date_from=date_from,
            force_date_to=date_to,
            queue="long",
            timeout=3600,
        )
        enqueued += 1

    logger.info("cron_historical : %s jobs enqueued.", enqueued)
