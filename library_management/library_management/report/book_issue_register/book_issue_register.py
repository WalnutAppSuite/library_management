# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _


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
		{"label": _("Return Date"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "book_status", "fieldtype": "Data", "width": 100},
		{"label": _("Reissued"), "fieldname": "reissue_count", "fieldtype": "Int", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	conditions = ["ltb.parenttype = 'Library Transactions'"]
	values = {}

	if filters.get("branch"):
		conditions.append("lt.branch = %(branch)s")
		values["branch"] = filters["branch"]
	if filters.get("book_status"):
		conditions.append("ltb.book_status = %(book_status)s")
		values["book_status"] = filters["book_status"]
	if filters.get("from_date"):
		conditions.append("ltb.issue_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("ltb.issue_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

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
			ltb.return_date,
			ltb.book_status,
			IFNULL(ltb.reissue_count, 0) AS reissue_count,
			lt.branch
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		LEFT JOIN `tabStudent` st ON st.name = lt.student
		WHERE {where}
		ORDER BY ltb.issue_date DESC, lt.name DESC
		""",
		values,
		as_dict=True,
	)
