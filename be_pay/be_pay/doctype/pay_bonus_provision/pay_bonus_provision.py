import frappe
from frappe.model.document import Document

class PayBonusProvision(Document):
    pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bonus_employees(doctype, txt, searchfield, start, page_len, filters):
	"""
	Retourne uniquement les employés actifs dont le Employment Type
	a have_bonus = 1.
	"""

	return frappe.db.sql(
		"""
		SELECT
			emp.name,
			emp.employee_name
		FROM `tabEmployee` emp
		INNER JOIN `tabEmployment Type` et
			ON et.name = emp.employment_type
		WHERE
			emp.status = 'Active'
			AND IFNULL(et.have_bonus, 0) = 1
			AND (
				emp.name LIKE %(txt)s
				OR emp.employee_name LIKE %(txt)s
			)
		ORDER BY emp.employee_name ASC
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)