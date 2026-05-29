app_name = "be_pay"
app_title = "Be Pay"
app_publisher = "ebamadernis@gmail.com"
app_description = "Fonctionnalités complementaires de la paie."
app_email = "ebamadernis@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "be_pay",
# 		"logo": "/assets/be_pay/logo.png",
# 		"title": "Be Pay",
# 		"route": "/be_pay",
# 		"has_permission": "be_pay.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/be_pay/css/be_pay.css"
# app_include_js = "/assets/be_pay/js/be_pay.js"

# include js, css files in header of web template
# web_include_css = "/assets/be_pay/css/be_pay.css"
# web_include_js = "/assets/be_pay/js/be_pay.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "be_pay/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "be_pay/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "be_pay.utils.jinja_methods",
# 	"filters": "be_pay.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "be_pay.install.before_install"
after_install = "be_pay.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "be_pay.uninstall.before_uninstall"
# after_uninstall = "be_pay.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "be_pay.utils.before_app_install"
# after_app_install = "be_pay.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "be_pay.utils.before_app_uninstall"
# after_app_uninstall = "be_pay.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "be_pay.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "be_pay.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------
scheduler_events = {
	"hourly": [
		"be_pay.tasks.cron",
        #"be_pay.tasks.every_minute"
	],
}

# scheduler_events = {
# 	"all": [
# 		"be_pay.tasks.all"
# 	],
# 	"daily": [
# 		"be_pay.tasks.daily"
# 	],
# 	"hourly": [
# 		"be_pay.tasks.hourly"
# 	],
# 	"weekly": [
# 		"be_pay.tasks.weekly"
# 	],
# 	"monthly": [
# 		"be_pay.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "be_pay.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "be_pay.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "be_pay.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "be_pay.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["be_pay.utils.before_request"]
# after_request = ["be_pay.utils.after_request"]

# Job Events
# ----------
# before_job = ["be_pay.utils.before_job"]
# after_job = ["be_pay.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"be_pay.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# DocType Class
# ---------------
# Override standard doctype classes
override_doctype_class = {
    "Employee": "be_pay.overrides.employee.CustomEmployee",
    "Salary Component": "be_pay.overrides.salary_component.CustomSalaryComponent",
    "Salary Slip": "be_pay.overrides.salary_slip.CustomSalarySlip",
    "Leave Application": "be_pay.overrides.leave_application.CustomLeaveApplication",
    "Loan": "be_pay.overrides.loan.CustomLoan",
    "Attendance": "be_pay.overrides.attendance.CustomAttendance",
    "Employee Checkin": "be_pay.overrides.employee_checkin.CustomEmployeeCheckin",
    "Item": "be_pay.overrides.item.CustomItem",
    "Leave Allocation": "be_pay.overrides.leave_allocation.CustomLeaveAllocation",
    "Payroll Period": "be_pay.overrides.payroll_period.CustomPayrollPeriod",
    "Payroll Entry": "be_pay.overrides.payroll_entry.CustomPayrollEntry",
    "Shift Type": "be_pay.overrides.shift_type.CustomShiftType",
}

# --- BEGIN AUTO-GENERATED ---
# Auto-generated by create_all.py
doc_events = {
    "Attendance": {
        "Before Insert": "be_pay.events.attendance.before_insert",
        "Before Save": "be_pay.events.attendance.before_save",
        "On Submit": "be_pay.events.attendance.on_submit",
        "On Cancel": "be_pay.events.attendance.on_cancel",
    },
    "Employee": {
        "Before Insert": "be_pay.events.employee.before_insert",
        "Before Save": "be_pay.events.employee.before_save",
    },
    "Employee Checkin": {
        "Before Save": "be_pay.events.employee_checkin.before_save",
    },
    "Item": {
        "Before Save": "be_pay.events.item.before_save",
    },
    "Leave Application": {
        "After Save": "be_pay.events.leave_application.after_save",
        "After Submit": "be_pay.events.leave_application.after_submit",
        "Before Submit": "be_pay.events.leave_application.before_submit",
    },
    "Loan": {
        "Before Cancel": "be_pay.events.loan.before_cancel",
    },
    "Salary Slip": {
        "After Insert": "be_pay.events.salary_slip.after_insert",
        "Before Insert": "be_pay.events.salary_slip.before_insert",
        "Before Save": "be_pay.events.salary_slip.before_save",
        "Before Submit": "be_pay.events.salary_slip.before_submit",
        "Before Validate": "be_pay.events.salary_slip.before_validate",
    },
}

doctype_js = {
    "Attendance": "public/js/attendance.js",
    "Employee": "public/js/employee.js",
    "Item": "public/js/item.js",
    "Leave Application": "public/js/leave_application.js",
    "Loan": "public/js/loan.js",
    "Loan Type": "public/js/loan_type.js",
    "Salary Slip": "public/js/salary_slip.js",
    "Payroll Entry": "public/js/payroll_entry.js",
    "Shift Type": "public/js/shift_type.js",
    "Pay Payroll Settings": "public/js/pay_payroll_settings.js",
}

override_whitelisted_methods = {
    "be_pay.api.get_employee_dependant2": "be_pay.api.get_employee_dependant2",
    "be_pay.api.test_api": "be_pay.api.test_api",
    "be_pay.api.get_emp_shift_in": "be_pay.api.get_emp_shift_in",
    "be_pay.api.get_emp_shift": "be_pay.api.get_emp_shift",
}

# --- END AUTO-GENERATED ---
fixtures = [
    # DocTypes maîtres du module Normalize
    "Pay Position Category",
    # Custom HTML Block pour le dashboard Leave
    "Custom HTML Block",
    # Customisations sur les doctypes ERPNext (exportées via bench export-fixtures)
    {"dt": "Custom Field", "filters": [["module", "=", "Be Pay"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Be Pay"]]},
    {"dt": "Client Script", "filters": [["enabled", "=", 1], ["module", "=", "Be Pay"]]},
    {"dt": "Server Script", "filters": [["disabled", "=", 0], ["module", "=", "Be Pay"]]},
    {"dt": "Print Format", "filters": [["disabled", "=", 0], ["module", "=", "Be Pay"]]},
]
