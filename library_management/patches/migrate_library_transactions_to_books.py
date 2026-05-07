import frappe
from frappe.utils import add_days, today


def execute():
	if not frappe.db.exists("DocType", "Library Transaction Book"):
		return

	for txn in frappe.get_all(
		"Library Transactions",
		fields=[
			"name",
			"isbn",
			"accession_number",
			"book_name",
			"author",
			"publisher",
			"date_of_issue",
			"return_date",
			"book_status",
		],
	):
		if frappe.db.count("Library Transaction Book", {"parent": txn.name, "parenttype": "Library Transactions"}):
			continue

		if not (txn.isbn or txn.accession_number or txn.book_name):
			continue

		book_name = None
		if txn.accession_number:
			book_name = frappe.db.get_value("Library Books", {"accession_number": txn.accession_number}, "name")
		if not book_name and txn.isbn:
			book_name = frappe.db.get_value("Library Books", {"isbn": txn.isbn}, "name")

		if not book_name:
			continue

		book = frappe.db.get_value(
			"Library Books",
			book_name,
			["isbn", "accession_number", "book_name", "author", "publisher"],
			as_dict=True,
		)
		issue_date = txn.date_of_issue or today()
		status = "RETURNED" if txn.book_status == "RETURNED" else "READING"
		frappe.get_doc(
			{
				"doctype": "Library Transaction Book",
				"parent": txn.name,
				"parenttype": "Library Transactions",
				"parentfield": "books",
				"library_book": book_name,
				"isbn": book.isbn,
				"accession_number": book.accession_number,
				"book_name": book.book_name,
				"author": book.author,
				"publisher": book.publisher,
				"issue_date": issue_date,
				"due_date": txn.return_date or add_days(issue_date, 7),
				"return_date": txn.return_date if status == "RETURNED" else None,
				"book_status": status,
			}
		).insert(ignore_permissions=True)
