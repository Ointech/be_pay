import frappe
from frappe import _

@frappe.whitelist()
def get_employee_dependant2():
    doc = frappe.get_doc('Employee','EMP0004')
    
    frappe.response['message'] = doc

@frappe.whitelist()
def test_api():
    script = "frappe.response['message'] = frappe.db.sql(\n  \"\"\"\n  SELECT t.employee, Max(t.`IN`) AS `IN`, Max(t.`OUT`) AS `OUT`\n  FROM(\n  select\n  distinct t3.employee, t3.time AS `IN`, NULL AS `OUT`\n  from\n  `tabEmployee` t1 LEFT JOIN \n  (SELECT *\n  FROM `tabAttendance` \n  WHERE attendance_date = DATE_ADD(CURDATE(), INTERVAL -1 DAY)) t2 ON t1.name = t2.employee \n  INNER JOIN `tabEmployee Checkin` t3 ON t1.name = t3.employee \n  where\n  t2.employee IS NULL\n  and t1.default_shift IS NULL\n  and t1.status = 'Active'\n  and CAST(t3.time AS DATE) = DATE_ADD(CURDATE(), INTERVAL -1 DAY)\n  and t3.log_type = 'IN'\n  UNION\n  select\n  distinct t3.employee, NULL AS `IN`, t3.time AS `OUT`\n  from\n  `tabEmployee` t1 LEFT JOIN \n  (SELECT *\n  FROM `tabAttendance` \n  WHERE attendance_date = DATE_ADD(CURDATE(), INTERVAL -1 DAY)) t2 ON t1.name = t2.employee \n  INNER JOIN `tabEmployee Checkin` t3 ON t1.name = t3.employee \n  where\n  t2.employee IS NULL\n  and t1.default_shift IS NULL\n  and t1.status = 'Active'\n  and ((CAST(t3.time AS DATE) >= DATE_ADD(CURDATE(), INTERVAL -1 DAY)\n  and TIME(t3.time) >= TIME('2009-05-18 12:00:57.005678'))\n  or \n  (CAST(t3.time AS DATE) >= CURDATE()\n  and TIME(t3.time) <= TIME('2009-05-18 12:00:57.005678'))\n  )\n  and t3.log_type = 'OUT'\n  ) AS t\n  GROUP BY t.employee\n  \"\"\"\n  #\n  as_dict=True\n )"
    exec(script, {"doc": doc, "frappe": frappe, "self": doc})

@frappe.whitelist()
def get_emp_shift_in():
    frappe.response['message'] = frappe.db.sql(
    	"""
    		select
    				distinct t3.employee, t3.log_type, t3.time
    			from
    				`tabEmployee` t1 LEFT JOIN  
    				(SELECT *
    				 FROM `tabAttendance` 
    				 WHERE attendance_date  = DATE_ADD(CURDATE(), INTERVAL -1 DAY)) t2 ON t1.name = t2.employee 
    				 INNER JOIN `tabEmployee Checkin` t3 ON t1.name = t3.employee 
    			where
    				t2.employee IS NULL
    				and t1.default_shift IS NULL
    				and t1.status = 'Active'
    				and  CAST(t3.time AS DATE)  = DATE_ADD(CURDATE(), INTERVAL -1 DAY)
    				and  t3.log_type = 'IN'
    	        
    	"""
    	,
    	as_dict=True
    )

@frappe.whitelist()
def get_emp_shift():
    frappe.response['message'] = frappe.db.sql(
    	"""
    		select
    				distinct t3.employee, t3.log_type, t3.time
    			from
    				`tabEmployee` t1 LEFT JOIN  
    				(SELECT *
    				 FROM `tabAttendance` 
    				 WHERE attendance_date  = DATE_ADD(CURDATE(), INTERVAL -1 DAY)) t2 ON t1.name = t2.employee 
    				 INNER JOIN `tabEmployee Checkin` t3 ON t1.name = t3.employee 
    			where
    				t2.employee IS NULL
    				and t1.default_shift IS NULL
    				and t1.status = 'Active'
    				and  CAST(t3.time AS DATE)  = DATE_ADD(CURDATE(), INTERVAL -1 DAY)
    	        
    	"""
    	,
    	as_dict=True
    )
