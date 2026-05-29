# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import today


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Student"), "fieldname": "student", "fieldtype": "Link", "options": "Student", "width": 140},
		{"label": _("Student Name"), "fieldname": "student_name", "fieldtype": "Data", "width": 180},
		{"label": _("Reference No"), "fieldname": "reference_number", "fieldtype": "Data", "width": 120},
		{"label": _("Book"), "fieldname": "library_book", "fieldtype": "Link", "options": "Library Books", "width": 110},
		{"label": _("Title"), "fieldname": "book_name", "fieldtype": "Data", "width": 200},
		{"label": _("Accession No"), "fieldname": "accession_number", "fieldtype": "Data", "width": 120},
		{"label": _("Issue Date"), "fieldname": "issue_date", "fieldtype": "Date", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Overdue Days"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	as_on = filters.get("as_on_date") or today()
	conditions = [
		"ltb.parenttype = 'Library Transactions'",
		"ltb.book_status = 'READING'",
		"ltb.due_date IS NOT NULL",
		"ltb.due_date < %(as_on)s",
	]
	values = {"as_on": as_on}

	if filters.get("branch"):
		conditions.append("lt.branch = %(branch)s")
		values["branch"] = filters["branch"]

	where = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			lt.student,
			st.student_name,
			st.reference_number,
			ltb.library_book,
			ltb.book_name,
			ltb.accession_number,
			ltb.issue_date,
			ltb.due_date,
			DATEDIFF(%(as_on)s, ltb.due_date) AS overdue_days,
			lt.branch
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		LEFT JOIN `tabStudent` st ON st.name = lt.student
		WHERE {where}
		ORDER BY overdue_days DESC
		""",
		values,
		as_dict=True,
	)
