# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, today

from library_management.services import _loan_period, sync_student_library_books


class LibraryTransactions(Document):
	def validate(self):
		self.validate_student_details()
		self.normalize_legacy_single_book()
		self.validate_books()

	def after_insert(self):
		self.update_book_inventory()
		sync_student_library_books(self.student, self)

	def on_update(self):
		self.update_book_inventory()
		sync_student_library_books(self.student, self)

	def validate_student_details(self):
		if not self.student:
			frappe.throw(_("Student is required"))

		student = frappe.get_value("Student", self.student, ["user", "program", "school"], as_dict=True)
		if student:
			self.student_email = self.student_email or student.user
			self.classs = self.classs or student.program
			self.branch = self.branch or student.school

	def normalize_legacy_single_book(self):
		if self.get("books") or not (self.isbn or self.accession_number or self.book_name):
			return

		book = None
		if self.accession_number:
			book = frappe.db.get_value("Library Books", {"accession_number": self.accession_number}, "name")
		if not book and self.isbn:
			book = frappe.db.get_value("Library Books", {"isbn": self.isbn}, "name")

		if not book:
			frappe.throw(_("No book found for this transaction"))

		book_doc = frappe.get_doc("Library Books", book)
		self.append(
			"books",
			{
				"library_book": book_doc.name,
				"isbn": book_doc.isbn,
				"accession_number": book_doc.accession_number,
				"book_name": book_doc.book_name,
				"author": book_doc.author,
				"publisher": book_doc.publisher,
				"issue_date": self.date_of_issue or today(),
				"due_date": self.return_date or add_days(self.date_of_issue or today(), _loan_period()),
				"return_date": self.return_date if self.book_status == "RETURNED" else None,
				"book_status": "RETURNED" if self.book_status == "RETURNED" else "READING",
			},
		)

	def validate_books(self):
		if not self.get("books"):
			frappe.throw(_("Add at least one book"))

		seen = set()
		for row in self.books:
			if not row.library_book:
				frappe.throw(_("Library Book is required in row {0}").format(row.idx))
			if row.library_book in seen:
				frappe.throw(_("Book {0} is already added").format(row.library_book))
			seen.add(row.library_book)

			book = frappe.get_doc("Library Books", row.library_book)
			row.isbn = row.isbn or book.isbn
			row.accession_number = row.accession_number or book.accession_number
			row.book_name = row.book_name or book.book_name
			row.author = row.author or book.author
			row.publisher = row.publisher or book.publisher
			row.issue_date = row.issue_date or today()
			row.due_date = row.due_date or add_days(row.issue_date, _loan_period())
			row.book_status = row.book_status or "READING"

			if row.book_status == "READING":
				self.validate_book_can_be_issued(book, row)
			elif row.book_status == "RETURNED" and not row.return_date:
				row.return_date = today()

			if row.return_date and row.issue_date and getdate(row.return_date) < getdate(row.issue_date):
				frappe.throw(_("Return date cannot be before issue date in row {0}").format(row.idx))

	def validate_book_can_be_issued(self, book, row):
		if book.status != "Active":
			frappe.throw(_("{0} is not active").format(book.book_name))
		if not cint(book.take_home):
			frappe.throw(_("{0} is not allowed for home reading").format(book.book_name))
		if self.branch and book.branch != self.branch:
			override_role = frappe.db.get_single_value("Library Management Settings", "branch_override_role") or "System Manager"
			if override_role not in frappe.get_roles():
				frappe.throw(_("{0} belongs to branch {1}").format(book.book_name, book.branch))

		already_issued = frappe.db.exists(
			"Library Transaction Book",
			{
				"library_book": book.name,
				"book_status": "READING",
				"parenttype": "Library Transactions",
				"name": ["!=", row.name],
			},
		)
		if already_issued:
			frappe.throw(_("{0} is already issued").format(book.book_name))

		was_already_reading = bool(row.name and frappe.db.get_value("Library Transaction Book", row.name, "book_status") == "READING")
		if cint(book.available_quantity) <= 0 and not was_already_reading:
			frappe.throw(_("{0} is not available").format(book.book_name))

	def update_book_inventory(self):
		for row in self.get("books") or []:
			if not row.library_book:
				continue
			available = 0 if row.book_status == "READING" else 1
			frappe.db.set_value("Library Books", row.library_book, "available_quantity", available)


def update_all_due_days():
	"""Compatibility hook for old scheduler references."""
	from library_management.services import update_all_due_days as update_rows

	return update_rows()
