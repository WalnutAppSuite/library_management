app_name = "library_management"
app_title = "Library Management"
app_publisher = "Frappe"
app_description = "App for managing Articles, Members, Memberships and Transactions for Libraries"
app_icon = "icon-book"
app_color = "#589494"
app_email = "info@frappe.io"
app_url = "https://frappe.io/apps/library_management"
app_version = "0.0.1"

after_install = "library_management.setup.install.after_install"
after_migrate = "library_management.migrate.after_migrate"

# Populate the virtual `custom_library_books` child table when a Student
# is loaded. Frappe v15 doesn't auto-fetch virtual child tables, so we
# fill it in on the onload event (fires when the form opens for editing).
doc_events = {
	"Student": {
		"onload": "library_management.services.populate_student_library_books_table",
	},
}

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/library_management/css/library_management.css"
# app_include_js = "/assets/library_management/js/library_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/library_management/css/library_management.css"
# web_include_js = "/assets/library_management/js/library_management.js"

# Installation
# ------------

# before_install = "library_management.install.before_install"
# after_install = "library_management.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "library_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.core.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.core.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"library_management.services.update_all_due_days"
	],
}

# scheduler_events = {
# 	"all": [
# 		"library_management.tasks.all"
# 	],
# 	"daily": [
# 		"library_management.tasks.daily"
# 	],
# 	"hourly": [
# 		"library_management.tasks.hourly"
# 	],
# 	"weekly": [
# 		"library_management.tasks.weekly"
# 	]
# 	"monthly": [
# 		"library_management.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "library_management.install.before_tests"
