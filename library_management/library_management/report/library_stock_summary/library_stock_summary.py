# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Book"), "fieldname": "name", "fieldtype": "Link", "options": "Library Books", "width": 110},
		{"label": _("Title"), "fieldname": "book_name", "fieldtype": "Data", "width": 220},
		{"label": _("ISBN"), "fieldname": "isbn", "fieldtype": "Data", "width": 130},
		{"label": _("Accession No"), "fieldname": "accession_number", "fieldtype": "Data", "width": 120},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "School", "width": 130},
		{"label": _("Room"), "fieldname": "room", "fieldtype": "Data", "width": 110},
		{"label": _("Shelf"), "fieldname": "book_shelf", "fieldtype": "Data", "width": 100},
		{"label": _("Quantity"), "fieldname": "quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Available"), "fieldname": "available_quantity", "fieldtype": "Int", "width": 90},
		{"label": _("Issued"), "fieldname": "issued", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("branch"):
		conditions.append("branch = %(branch)s")
		values["branch"] = filters["branch"]
	if filters.get("room"):
		conditions.append("room = %(room)s")
		values["room"] = filters["room"]
	if filters.get("book_shelf"):
		conditions.append("book_shelf = %(book_shelf)s")
		values["book_shelf"] = filters["book_shelf"]
	if filters.get("only_low_stock"):
		conditions.append("IFNULL(available_quantity, 0) <= 0")

	where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
	rows = frappe.db.sql(
		f"""
		SELECT
			name,
			book_name,
			isbn,
			accession_number,
			branch,
			room,
			book_shelf,
			quantity,
			available_quantity,
			status
		FROM `tabLibrary Books`
		{where}
		ORDER BY branch ASC, book_shelf ASC, book_name ASC
		""",
		values,
		as_dict=True,
	)
	for row in rows:
		row["issued"] = max(cint(row.get("quantity")) - cint(row.get("available_quantity")), 0)
	return rows
