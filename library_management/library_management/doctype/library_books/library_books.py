# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_link_to_form


class LibraryBooks(Document):
	def validate(self):
		self.quantity = cint(self.quantity) or 1
		if self.available_quantity is None:
			self.available_quantity = self.quantity
		if self.accession_number and self.branch:
			existing = frappe.get_value(
				"Library Books",
				{"accession_number": self.accession_number, "branch": self.branch},
				["name", "book_name"],
				as_dict=True,
			)
			if existing and existing.name != self.name:
				book_link = get_link_to_form("Library Books", existing.name)
				frappe.throw(
					_("Accession number {0} already exists for branch {1} and is already linked with book {2}.").format(
						self.accession_number,
						self.branch,
						book_link,
					)
				)
