# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Book"), "fieldname": "name", "fieldtype": "Link", "options": "Library Books", "width": 110},
		{"label": _("Title"), "fieldname": "book_name", "fieldtype": "Data", "width": 240},
		{"label": _("ISBN"), "fieldname": "isbn", "fieldtype": "Data", "width": 130},
		{"label": _("Accession No"), "fieldname": "accession_number", "fieldtype": "Data", "width": 120},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "School", "width": 130},
		{"label": _("Shelf"), "fieldname": "book_shelf", "fieldtype": "Data", "width": 100},
		{"label": _("Available"), "fieldname": "available_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Reason"), "fieldname": "reason", "fieldtype": "Data", "width": 160},
	]


def get_data(filters):
	conditions = ["(IFNULL(available_quantity, 0) <= 0 OR status IN ('Inactive', 'Discontinued'))"]
	values = {}

	if filters.get("branch"):
		conditions.append("branch = %(branch)s")
		values["branch"] = filters["branch"]
	if filters.get("status"):
		conditions.append("status = %(status)s")
		values["status"] = filters["status"]

	where = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			book_name,
			isbn,
			accession_number,
			branch,
			book_shelf,
			available_quantity,
			status
		FROM `tabLibrary Books`
		WHERE {where}
		ORDER BY status ASC, branch ASC, book_name ASC
		""",
		values,
		as_dict=True,
	)
	for row in rows:
		reasons = []
		if (row.get("available_quantity") or 0) <= 0:
			reasons.append(_("No copies available"))
		if row.get("status") in ("Inactive", "Discontinued"):
			reasons.append(row.get("status"))
		row["reason"] = ", ".join(reasons)
	return rows
