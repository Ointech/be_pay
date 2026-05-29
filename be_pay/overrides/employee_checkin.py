# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Employee Checkin pour Be Pay.

Fusionne deux logiques :
1. Avant sauvegarde  : assignation automatique du shift (Matin / Midi / Soir / Nuit).
2. Après insertion  : création / mise à jour de l'Attendance liée avec calcul
                      des heures, late_entry, early_exit et prise en compte
                      des Shift Assignments et Attendance Requests.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, get_datetime_str, get_time, getdate, add_days, time_diff_in_hours
from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin


# =============================================================================
# CONSTANTES : plages horaires pour la détection automatique des 4 shifts
# =============================================================================
SHIFT_RANGES = {
    "Matin": {"in_start": 5, "in_end": 10, "start": "07:00:00", "end": "15:00:00"},
    "Midi":  {"in_start": 9,  "in_end": 14, "start": "11:00:00", "end": "19:00:00"},
    "Soir":  {"in_start": 13, "in_end": 18, "start": "15:00:00", "end": "23:00:00"},
    "Nuit":  {"in_start": 20, "in_end": 3,  "start": "23:00:00", "end": "07:00:00"},
}

# Heures de travail attendues par shift (en décimal)
SHIFT_EXPECTED_HOURS = 8.0


class CustomEmployeeCheckin(EmployeeCheckin):
    """
    Classe unique fusionnée pour la logique Be Pay sur Employee Checkin.
    """

    # =====================================================================
    # CONFIG : lecture du paramètre Pay Payroll Settings
    # =====================================================================
    def _be_pay_use_shift_assignment(self):
        """
        Retourne True si le paramètre 'Use Shift Assignment for Attendance'
        est activé dans Pay Payroll Settings. Dans ce cas, le shift est
        déterminé UNIQUEMENT par les Shift Assignments officiels, et non
        par l'heure du pointage.
        """
        try:
            return frappe.db.get_single_value(
                "Pay Payroll Settings", "use_shift_assignment_for_attendance"
            )
        except Exception:
            return 0

    # =====================================================================
    # BEFORE SAVE : détection et assignation automatique du shift
    # =====================================================================
    def before_save(self):
        """
        Avant sauvegarde :
        - Si 'Use Shift Assignment for Attendance' est coché : on laisse
          HRMS gérer le shift nativement via fetch_shift() (qui utilise
          les Shift Assignment). On ne fait PAS l'auto-détection.
        - Sinon : on applique l'auto-détection du shift selon l'heure du
          pointage (logique Be Pay historique).
        """
        if not self._be_pay_use_shift_assignment():
            self._be_pay_auto_assign_shift()

        # La classe parente EmployeeCheckin ne définit pas toujours before_save()
        parent_before_save = getattr(super(), "before_save", None)
        if parent_before_save:
            parent_before_save()

    def _be_pay_auto_assign_shift(self):
        """
        Détecte le shift (Matin, Midi, Soir, Nuit) en fonction de l'heure
        du pointage et pré-remplit shift_start / shift_end / shift_actual_start
        / shift_actual_end pour que HRMS puisse calculer les heures correctement.
        """
        if not self.time or self.shift:
            return

        punch_dt = get_datetime(self.time)
        punch_hour = punch_dt.hour
        log_type = self.log_type
        date_str = str(punch_dt.date())

        detected_shift = None

        # ---------------------------------------------------------------
        # Détection par heure du premier IN (ou du OUT pour confirmation)
        # ---------------------------------------------------------------
        for shift_name, cfg in SHIFT_RANGES.items():
            in_start = cfg["in_start"]
            in_end = cfg["in_end"]

            # Cas spécial Nuit (chevauche minuit)
            if shift_name == "Nuit":
                if punch_hour >= in_start or punch_hour <= in_end:
                    detected_shift = shift_name
                    break
            else:
                if in_start <= punch_hour <= in_end:
                    detected_shift = shift_name
                    break

        if not detected_shift:
            return

        self.shift = detected_shift
        cfg = SHIFT_RANGES[detected_shift]

        shift_start_str = f"{date_str} {cfg['start']}"
        shift_end_str = f"{date_str} {cfg['end']}"

        # Pour le shift Nuit, la fin est le lendemain matin
        if detected_shift == "Nuit":
            shift_end_dt = get_datetime(shift_end_str)
            if log_type == "OUT":
                # Le OUT du matin appartient au shift de la veille
                self.shift_start = add_days(get_datetime(shift_start_str), -1)
                self.shift_end = shift_end_dt
                self.shift_actual_start = add_days(get_datetime(shift_start_str), -1)
                self.shift_actual_end = shift_end_dt
            else:
                # IN le soir → shift commence ce soir, finit demain matin
                self.shift_start = get_datetime(shift_start_str)
                self.shift_end = add_days(shift_end_dt, 1)
                self.shift_actual_start = get_datetime(shift_start_str)
                self.shift_actual_end = add_days(shift_end_dt, 1)
        else:
            self.shift_start = get_datetime(shift_start_str)
            self.shift_end = get_datetime(shift_end_str)
            # Marges de 2h avant le début et après la fin
            self.shift_actual_start = add_days(get_datetime(shift_start_str), 0)
            self.shift_actual_end = add_days(get_datetime(shift_end_str), 0)

    # =====================================================================
    # AFTER INSERT : création / mise à jour de l'Attendance
    # =====================================================================
    def after_insert(self):
        """
        Après insertion d'un Employee Checkin :
        - récupère tous les pointages de la journée
        - détermine first_in / last_out
        - vérifie Shift Assignment et Attendance Request
        - calcule late_entry / early_exit / heures
        - crée ou met à jour l'Attendance
        """
        frappe.logger().info(
            "Be Pay Checkin after_insert : %s | %s | %s", self.employee, self.log_type, self.time
        )
        self._be_pay_process_attendance()

    # -----------------------------------------------------------------
    # SECTION : fonctions utilitaires privées
    # -----------------------------------------------------------------
    def _be_pay_get_day_checkins(self, employee, checkin_date):
        """
        Récupère tous les Employee Checkin de `employee` pour `checkin_date`.
        Retourne une liste de dicts triés par time croissant.
        """
        return frappe.get_all(
            "Employee Checkin",
            filters={
                "employee": employee,
                "time": ["between", [f"{checkin_date} 00:00:00", f"{checkin_date} 23:59:59"]],
            },
            fields=["name", "log_type", "time", "shift"],
            order_by="time asc",
        )

    def _be_pay_get_first_in_last_out(self, checkins):
        """
        Depuis une liste de checkins, retourne (first_in_datetime, last_out_datetime).
        Ignore les checkins dont le champ `time` ne peut pas être parsé en datetime.
        """
        first_in = None
        last_out = None
        for c in checkins:
            c_dt = get_datetime(c.time)
            if not c_dt:
                # Protection : si `time` est un objet `time` ou une valeur invalide,
                # `get_datetime` retourne None. On ignore ce checkin.
                continue
            if c.log_type == "IN":
                if first_in is None or c_dt < first_in:
                    first_in = c_dt
            elif c.log_type == "OUT":
                if last_out is None or c_dt > last_out:
                    last_out = c_dt
        return first_in, last_out

    def _be_pay_get_shift_assignment(self, employee, for_date):
        """
        Retourne le Shift Type assigné à l'employé pour `for_date`.
        On utilise l'API standard get_employee_shift de HRMS.
        """
        from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

        try:
            shift_data = get_employee_shift(
                employee,
                for_timestamp=get_datetime(f"{for_date} 12:00:00"),
                consider_default_shift=True,
            )
            if shift_data and shift_data.get("shift_type"):
                return frappe.get_doc("Shift Type", shift_data["shift_type"].name)
        except Exception:
            frappe.logger().warning(
                "Erreur récupération shift pour %s le %s", employee, for_date, exc_info=True
            )
        return None

    def _be_pay_get_attendance_request(self, employee, for_date):
        """
        Retourne un Attendance Request approuvé (docstatus=1) couvrant `for_date`.
        Si trouvé, cela signifie que l'employé a une dérogation.
        """
        requests = frappe.get_all(
            "Attendance Request",
            filters={
                "employee": employee,
                "docstatus": 1,
                "from_date": ["<=", for_date],
                "to_date": [">=", for_date],
            },
            fields=["name", "reason"],
            limit=1,
        )
        return requests[0] if requests else None

    def _be_pay_calculate_working_hours(self, first_in, last_out):
        """
        Calcule les heures effectives entre first_in et last_out.
        Gère le cas où last_out est le lendemain (shift nuit).
        Retourne (hours_str HH:MM, hours_dec décimal).
        """
        if not first_in or not last_out:
            return None, 0.0

        if last_out < first_in:
            last_out = add_days(last_out, 1)

        diff = last_out - first_in
        total_seconds = diff.total_seconds()
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        hours_str = f"{h:02d}:{m:02d}"
        hours_dec = round(total_seconds / 3600, 2)
        return hours_str, hours_dec

    def _be_pay_calculate_late_early(self, first_in, last_out, shift_doc, has_attendance_request):
        """
        Calcule late_entry et early_exit selon les heures du Shift Type.

        Règles :
        - Si Attendance Request existe : late_entry n'est JAMAIS marqué
          (l'employé peut arriver quand il veut), mais early_exit est
          TOUJOURS vérifié.
        - Sinon : on compare first_in avec start_time + grace_period et
          last_out avec end_time - grace_period.

        Retourne (late_entry, early_exit) booleens.
        """
        late_entry = 0
        early_exit = 0

        if not shift_doc:
            return late_entry, early_exit

        shift_start = get_time(shift_doc.start_time)
        shift_end = get_time(shift_doc.end_time)

        # ---------------------------------------------------------------
        # Grace periods depuis le Shift Type (minutes)
        # ---------------------------------------------------------------
        late_grace = 0
        early_grace = 0
        if getattr(shift_doc, "enable_late_entry_marking", 0):
            late_grace = getattr(shift_doc, "late_entry_grace_period", 0) or 0
        if getattr(shift_doc, "enable_early_exit_marking", 0):
            early_grace = getattr(shift_doc, "early_exit_grace_period", 0) or 0

        # ---------------------------------------------------------------
        # Late Entry
        # ---------------------------------------------------------------
        if not has_attendance_request and first_in:
            # Heure limite d'arrivée = start_time + grace_period
            from datetime import timedelta as td

            start_dt = get_datetime(f"{first_in.date()} {shift_start}")
            limit_in = start_dt + td(minutes=late_grace)

            if first_in > limit_in:
                late_entry = 1

        # ---------------------------------------------------------------
        # Early Exit (toujours vérifié, même avec Attendance Request)
        # ---------------------------------------------------------------
        if last_out:
            from datetime import timedelta as td

            # Pour un shift normal, la date de sortie est la même que celle
            # de l'entrée. Pour un shift de nuit, la fin est au lendemain.
            reference_date = first_in.date() if first_in else last_out.date()
            end_dt = get_datetime(f"{reference_date} {shift_end}")

            if shift_end <= shift_start:
                end_dt = add_days(end_dt, 1)

            limit_out = end_dt - td(minutes=early_grace)
            if last_out < limit_out:
                early_exit = 1

        return late_entry, early_exit

    def _be_pay_get_or_create_attendance(self, employee, attendance_date, shift_name, employment_type):
        """
        Retourne une Attendance existante ou prépare une nouvelle Attendance.

        Important : une nouvelle Attendance n'est pas insérée ici. Elle est
        insérée uniquement dans `_be_pay_update_attendance`, après affectation
        correcte de `in_time` et `out_time` au format DateTime.
        """
        existing = frappe.get_all(
            "Attendance",
            filters={
                "employee": employee,
                "attendance_date": attendance_date,
            },
            fields=["name"],
            limit=1,
        )

        if existing:
            return frappe.get_doc("Attendance", existing[0].name)

        # Préparer une nouvelle Attendance, sans insert/submit immédiat.
        attendance = frappe.new_doc("Attendance")
        attendance.employee = employee
        attendance.attendance_date = attendance_date

        # Déterminer le statut par défaut selon le type d'emploi.
        if employment_type == "Nationaux":
            attendance.status = "Present"
            attendance.shift = shift_name
        else:
            # Si le Leave Type "P" existe, l'utiliser ; sinon mettre Present.
            if frappe.db.exists("Leave Type", "P"):
                attendance.status = "On Leave"
                attendance.leave_type = "P"
            else:
                attendance.status = "Present"

            # Si le Shift Type "P" existe, l'utiliser ; sinon utiliser le shift détecté.
            if frappe.db.exists("Shift Type", "P"):
                attendance.shift = "P"
            else:
                attendance.shift = shift_name

        return attendance

    def _be_pay_update_attendance(
        self,
        attendance,
        first_in,
        last_out,
        working_hours_dec,
        hours_control,
        late_entry,
        early_exit,
        shift_name,
    ):
        """
        Crée ou met à jour l'Attendance avec des valeurs DateTime valides.

        Le correctif principal consiste à toujours convertir `first_in` et
        `last_out` en datetime complet via `get_datetime` avant de les stocker.
        Si la conversion échoue (ex. objet `time` seul), le champ est ignoré
        pour éviter l'erreur MySQL 1292.
        """
        updates = {}

        if first_in:
            dt_in = get_datetime(first_in)
            if dt_in:
                updates["in_time"] = get_datetime_str(dt_in)
            else:
                frappe.logger().warning(
                    "Be Pay | first_in non convertible en datetime : %s (%s)",
                    first_in,
                    type(first_in).__name__,
                )

        if last_out:
            dt_out = get_datetime(last_out)
            if dt_out:
                updates["out_time"] = get_datetime_str(dt_out)
            else:
                frappe.logger().warning(
                    "Be Pay | last_out non convertible en datetime : %s (%s)",
                    last_out,
                    type(last_out).__name__,
                )

        if working_hours_dec is not None:
            updates["working_hours"] = working_hours_dec
        if hours_control is not None:
            updates["hours_control"] = hours_control
        if late_entry is not None:
            updates["late_entry"] = late_entry
        if early_exit is not None:
            updates["early_exit"] = early_exit
        if shift_name:
            updates["shift"] = shift_name

        if not updates:
            return

        if attendance.is_new():
            # Pour une nouvelle Attendance, définir les DateTime avant INSERT.
            for fieldname, value in updates.items():
                attendance.set(fieldname, value)

            attendance.insert(ignore_permissions=True)
            attendance.submit()
            return

        # Pour une Attendance existante déjà soumise, mettre à jour les champs
        # calculés sans repasser par les validations qui pourraient les écraser.
        frappe.db.set_value(
            "Attendance",
            attendance.name,
            updates,
            update_modified=True,
        )

    # -----------------------------------------------------------------
    # SECTION : logique principale de traitement de l'Attendance
    # -----------------------------------------------------------------
    def _be_pay_process_night_shift_out(self, employee, yesterday_date, prev_first_in, punch_dt):
        """
        Traite spécifiquement le OUT d'un shift nuit :
        met à jour l'Attendance de la veille avec le vrai OUT du matin.
        """
        # Récupérer le shift de la veille
        shift_doc = self._be_pay_get_shift_assignment(employee, yesterday_date)
        shift_name = shift_doc.name if shift_doc else (self.shift or "")

        # Vérifier si une dérogation existe pour la veille
        attendance_request = self._be_pay_get_attendance_request(employee, yesterday_date)
        has_attendance_request = bool(attendance_request)

        # Calculer les heures réelles du shift nuit
        _, working_hours = self._be_pay_calculate_working_hours(prev_first_in, punch_dt)

        expected_hours = SHIFT_EXPECTED_HOURS
        if shift_doc:
            start_t = get_time(shift_doc.start_time)
            end_t = get_time(shift_doc.end_time)
            if end_t <= start_t:
                expected_hours = time_diff_in_hours(
                    get_datetime(f"2000-01-02 {end_t}"),
                    get_datetime(f"2000-01-01 {start_t}"),
                )

        hours_control = round(working_hours - expected_hours, 2) if working_hours else 0.0

        # Early_exit toujours vérifié ; late_entry jamais vérifié si dérogation
        late_entry, early_exit = self._be_pay_calculate_late_early(
            prev_first_in, punch_dt, shift_doc, has_attendance_request
        )

        prev_attendance = frappe.get_all(
            "Attendance",
            filters={"employee": employee, "attendance_date": yesterday_date},
            fields=["name"],
            limit=1,
        )

        if prev_attendance:
            prev_doc = frappe.get_doc("Attendance", prev_attendance[0].name)
            self._be_pay_update_attendance(
                prev_doc,
                prev_first_in,
                punch_dt,
                working_hours,
                hours_control,
                late_entry,
                early_exit,
                shift_name,
            )

    def _be_pay_process_attendance(self):
        """
        Orchestration complète :
        1. Détecte le cas spécial du shift Nuit (OUT le lendemain).
        2. Récupère les checkins de la journée.
        3. Détermine first_in / last_out.
        4. Vérifie Shift Assignment et Attendance Request.
        5. Calcule les heures et les flags.
        6. Met à jour ou crée l'Attendance.
        """
        employee = self.employee
        punch_dt = get_datetime(self.time)
        punch_date = punch_dt.date()

        # ---------------------------------------------------------------
        # 0. CAS SPÉCIAL : OUT du shift Nuit (avant 09h, IN veille après 20h)
        #    On traite ce cas en premier pour ne pas créer d'Attendance
        #    parasite pour le jour du OUT.
        # ---------------------------------------------------------------
        if self.log_type == "OUT" and punch_dt.hour < 9:
            yesterday = str(add_days(punch_date, -1))
            prev_checkins = self._be_pay_get_day_checkins(employee, yesterday)
            prev_first_in, _ = self._be_pay_get_first_in_last_out(prev_checkins)

            if prev_first_in and prev_first_in.hour >= 20:
                self._be_pay_process_night_shift_out(employee, yesterday, prev_first_in, punch_dt)
                return

        # ---------------------------------------------------------------
        # 1. Tous les pointages de la journée
        # ---------------------------------------------------------------
        day_checkins = self._be_pay_get_day_checkins(employee, punch_date)
        first_in, last_out = self._be_pay_get_first_in_last_out(day_checkins)

        # ---------------------------------------------------------------
        # 2. Récupérer les infos employé
        # ---------------------------------------------------------------
        emp_doc = frappe.get_doc("Employee", employee)
        employment_type = emp_doc.employment_type

        # ---------------------------------------------------------------
        # 3. Déterminer le shift de référence
        # ---------------------------------------------------------------
        use_shift_assignment = self._be_pay_use_shift_assignment()
        shift_doc = self._be_pay_get_shift_assignment(employee, punch_date)

        if use_shift_assignment:
            # Mode Shift Assignment uniquement : pas de fallback sur l'auto-détection
            if not shift_doc:
                frappe.logger().warning(
                    "Be Pay | Mode Shift Assignment actif : aucun Shift Assignment trouvé "
                    "pour %s le %s. Attendance non créée.", employee, punch_date
                )
                return
            shift_name = shift_doc.name
        else:
            # Mode historique : Priorité Shift Assignment > auto-détecté
            # Si le checkin existant n'a pas de shift (créé en mode=1), on tente
            # l'auto-détection à la volée pour ne pas perdre les Attendance.
            if not self.shift:
                self._be_pay_auto_assign_shift()
            shift_name = shift_doc.name if shift_doc else (self.shift or "")

        # ---------------------------------------------------------------
        # 4. Vérifier Attendance Request (dérogation)
        # ---------------------------------------------------------------
        attendance_request = self._be_pay_get_attendance_request(employee, punch_date)
        has_attendance_request = bool(attendance_request)

        # ---------------------------------------------------------------
        # 5. Calcul des heures
        # ---------------------------------------------------------------
        hours_str, working_hours_dec = self._be_pay_calculate_working_hours(first_in, last_out)

        # Heures attendues = durée du shift ou 8h par défaut
        expected_hours = SHIFT_EXPECTED_HOURS
        if shift_doc:
            start_t = get_time(shift_doc.start_time)
            end_t = get_time(shift_doc.end_time)
            if end_t > start_t:
                expected_hours = time_diff_in_hours(
                    get_datetime(f"2000-01-01 {end_t}"),
                    get_datetime(f"2000-01-01 {start_t}"),
                )
            else:
                # Shift nuit
                expected_hours = time_diff_in_hours(
                    get_datetime(f"2000-01-02 {end_t}"),
                    get_datetime(f"2000-01-01 {start_t}"),
                )

        hours_control = round(working_hours_dec - expected_hours, 2) if working_hours_dec else 0.0

        # ---------------------------------------------------------------
        # 6. Late Entry / Early Exit
        # ---------------------------------------------------------------
        late_entry, early_exit = self._be_pay_calculate_late_early(
            first_in, last_out, shift_doc, has_attendance_request
        )

        # ---------------------------------------------------------------
        # 7. Créer / Mettre à jour l'Attendance
        # ---------------------------------------------------------------
        attendance = self._be_pay_get_or_create_attendance(
            employee, punch_date, shift_name, employment_type
        )

        self._be_pay_update_attendance(
            attendance,
            first_in,
            last_out,
            working_hours_dec,
            hours_control,
            late_entry,
            early_exit,
            shift_name,
        )
