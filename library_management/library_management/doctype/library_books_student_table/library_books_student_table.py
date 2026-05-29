# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LibraryBooksStudentTable(Document):
	@staticmethod
	def get_list(args):
		# Frappe may call this with:
		#  - args["filters"] as a dict: {"parent": <student_name>, ...}
		#  - args["filters"] as a list of [field, op, value] tuples.
		filters = args.get("filters") or {}
		student = None
		if isinstance(filters, dict):
			student = filters.get("parent")
		elif isinstance(filters, list):
			for f in filters:
				if not isinstance(f, (list, tuple)):
					continue
				if len(f) >= 3 and f[0] == "parent":
					student = f[2]
					break
				if len(f) == 2 and f[0] == "parent":
					student = f[1]
					break
		return rows_for_student(student)


def rows_for_student(student):
	"""Return Library Books Student Table rows for the given student.

	Used both by:
	- LibraryBooksStudentTable.get_list — for direct list calls.
	- The Student onload doc_event — to populate the virtual
	  custom_library_books child table when the form is loaded
	  (Frappe v15 doesn't auto-fetch virtual child tables on parent load).

	Each row's `parent` is the Student name so the framework accepts it
	as a child of the loaded Student doc.
	"""
	if not student:
		return []
	return frappe.db.sql(
		"""
		SELECT
			ltb.name,
			%(student)s          AS parent,
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
			IFNULL(ltb.reissue_count, 0) AS reissue_count,
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
