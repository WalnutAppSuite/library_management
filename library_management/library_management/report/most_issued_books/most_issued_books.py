# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Book"), "fieldname": "library_book", "fieldtype": "Link", "options": "Library Books", "width": 120},
		{"label": _("Title"), "fieldname": "book_name", "fieldtype": "Data", "width": 240},
		{"label": _("Author"), "fieldname": "author", "fieldtype": "Data", "width": 160},
		{"label": _("Accession No"), "fieldname": "accession_number", "fieldtype": "Data", "width": 120},
		{"label": _("Total Issues"), "fieldname": "total_issues", "fieldtype": "Int", "width": 110},
		{"label": _("Currently Issued"), "fieldname": "currently_issued", "fieldtype": "Int", "width": 130},
	]


def get_data(filters):
	conditions = ["ltb.parenttype = 'Library Transactions'"]
	values = {}

	if filters.get("branch"):
		conditions.append("lt.branch = %(branch)s")
		values["branch"] = filters["branch"]
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
			ltb.library_book,
			ltb.book_name,
			ltb.author,
			ltb.accession_number,
			COUNT(*) AS total_issues,
			SUM(CASE WHEN ltb.book_status = 'READING' THEN 1 ELSE 0 END) AS currently_issued
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		WHERE {where}
		GROUP BY ltb.library_book, ltb.book_name, ltb.author, ltb.accession_number
		ORDER BY total_issues DESC, ltb.book_name ASC
		""",
		values,
		as_dict=True,
	)
