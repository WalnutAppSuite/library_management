# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LibraryBooksStudentTable(Document):
	@staticmethod
	def get_list(args):
		filters = args.get("filters") or {}
		student = filters.get("parent")
		if not student:
			return []

		return frappe.db.sql(
			"""
			SELECT
				ltb.name,
				lt.name              AS parent,
				'Student'            AS parenttype,
				'custom_library_books' AS parentfield,
				ltb.isbn             AS book_id,
				ltb.book_name,
				ltb.author,
				ltb.accession_number AS reference_number,
				ltb.issue_date       AS book_issue_date,
				ltb.return_date      AS book_return_date,
				CASE
					WHEN ltb.issue_date IS NOT NULL AND ltb.due_date IS NOT NULL
					THEN CONCAT(DATEDIFF(ltb.due_date, ltb.issue_date), ' days')
					ELSE ''
				END                  AS reading_period,
				ltb.book_status,
				CASE
					WHEN ltb.book_status = 'READING'
					     AND ltb.due_date IS NOT NULL
					     AND ltb.due_date < CURDATE()
					THEN CONCAT(DATEDIFF(CURDATE(), ltb.due_date), ' days')
					ELSE '0 days'
				END                  AS due__days,
				1                    AS take_home,
				lt.name              AS library_transaction,
				ltb.name             AS library_transaction_book
			FROM `tabLibrary Transaction Book` ltb
			JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
			WHERE lt.student = %(student)s
			  AND ltb.parenttype = 'Library Transactions'
			ORDER BY ltb.issue_date DESC, lt.modified DESC
			""",
			{"student": student},
			as_dict=True,
		)
