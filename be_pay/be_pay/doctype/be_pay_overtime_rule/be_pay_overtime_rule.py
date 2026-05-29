# Copyright (c) 2026, Be Pay and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BePayOvertimeRule(Document):
	def validate(self):
		self._normalize_fieldname()
		self._ensure_custom_field()

	def _normalize_fieldname(self):
		if self.target_fieldname:
			fieldname = self.target_fieldname.strip().lower().replace(" ", "_")
			if not fieldname.startswith("custom_"):
				fieldname = "custom_" + fieldname
			self.target_fieldname = fieldname

	def _ensure_custom_field(self):
		if not self.target_fieldname or not self.target_label:
			return

		existing = frappe.db.get_value(
			"Custom Field",
			{"dt": "Pay Attendance Line", "fieldname": self.target_fieldname},
		)

		cf_data = {
			"dt": "Pay Attendance Line",
			"fieldname": self.target_fieldname,
			"label": self.target_label,
			"fieldtype": "Float",
			"insert_after": "hours",
			"module": "Be Pay",
			"read_only": 0,
			"hidden": 0,
		}

		if existing:
			cf = frappe.get_doc("Custom Field", existing)
			for k, v in cf_data.items():
				setattr(cf, k, v)
			cf.save(ignore_permissions=True)
		else:
			cf = frappe.new_doc("Custom Field")
			for k, v in cf_data.items():
				setattr(cf, k, v)
			cf.insert(ignore_permissions=True)

		frappe.clear_cache(doctype="Pay Attendance Line")

	def on_trash(self):
		if self.target_fieldname:
			existing = frappe.db.get_value(
				"Custom Field",
				{"dt": "Pay Attendance Line", "fieldname": self.target_fieldname},
			)
			if existing:
				frappe.delete_doc("Custom Field", existing, force=1)
				frappe.clear_cache(doctype="Pay Attendance Line")
