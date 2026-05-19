# Copyright (c) 2025, Be Pay
# License: MIT

"""
Override du DocType Payroll Period pour Be Pay.

Génère automatiquement le name sous la forme : {name_saisi}-{fiscal_year}
lorsque l'application Be Pay est installée et que le champ fiscal_year est renseigné.

Attention : avec autoname='Prompt', Frappe lit __newname et retourne AVANT
d'appeler autoname(). On utilise donc before_insert() pour modifier __newname
juste avant set_new_name().

ATTENTION au name mangling Python : self.__newname cree _CustomPayrollPeriod__newname.
Il faut utiliser setattr(self, "__newname", ...) pour que Frappe puisse la lire.
"""

import frappe
from hrms.payroll.doctype.payroll_period.payroll_period import PayrollPeriod


class CustomPayrollPeriod(PayrollPeriod):
	"""
	Extension de la classe Payroll Period pour la logique Be Pay.
	"""

	def before_insert(self):
		"""
		Modifie __newname avant que le framework ne traite la règle Prompt.
		"""
		fiscal_year = self.get("fiscal_year")
		if fiscal_year:
			typed_name = self.get("__newname") or self.get("name")
			if typed_name and not str(typed_name).startswith("New "):
				typed_name = str(typed_name).strip()
				fiscal_year = str(fiscal_year).strip()
				# NE PAS utiliser self.__newname = ... (name mangling Python)
				# Frappe lit __newname via self.get("__newname")
				setattr(self, "__newname", f"{typed_name}-{fiscal_year}")

	def autoname(self):
		"""
		Fallback pour les créations sans __newname (API, import, etc.).
		"""
		fiscal_year = self.get("fiscal_year")
		typed_name = self.get("__newname") or self.get("name")

		if fiscal_year and typed_name and not str(typed_name).startswith("New "):
			self.name = f"{str(typed_name).strip()}-{str(fiscal_year).strip()}"
			return

		# Le parent n'a pas forcément autoname() ; si c'est le cas,
		# le framework continuera avec les règles de naming par défaut.
		parent_autoname = getattr(super(), "autoname", None)
		if parent_autoname:
			parent_autoname()
