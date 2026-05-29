# Copyright (c) 2026, ebamadernis@gmail.com and contributors
# For license information, please see license.txt

from datetime import time

from frappe.utils import flt, get_time
from hrms.hr.doctype.shift_type.shift_type import ShiftType


class CustomShiftType(ShiftType):
	"""
	Extension du DocType Shift Type.

	Calcule automatiquement le nombre normal d'heures du shift
	à partir de l'heure de début et de l'heure de fin.
	"""

	def validate(self):
		# Conserver toutes les validations standards de HRMS :
		# - heure de début différente de l'heure de fin
		# - validation des shifts circulaires
		# - contrôle des pointages non liés
		super().validate()

		self.calculate_normal_working_hours()

	def calculate_normal_working_hours(self) -> None:
		"""
		Calcule la durée normale du shift, y compris lorsqu'il
		commence un jour et se termine le jour suivant.

		Exemples :
			08:00 - 17:00 = 9.00 heures
			20:00 - 06:00 = 10.00 heures
			22:30 - 06:15 = 7.75 heures
		"""

		start_time: time = get_time(self.start_time)
		end_time: time = get_time(self.end_time)

		shift_start, shift_end = self.get_shift_start_and_shift_end(
			start_time,
			end_time
		)

		duration_in_hours = (shift_end - shift_start).total_seconds() / 3600

		self.hours = flt(duration_in_hours, 2)