# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LibraryBooks(Document):
	def validate(self):
		if not self.quantity:
			self.quantity = 1
		if self.available_quantity is None:
			self.available_quantity = self.quantity
		if self.accession_number and self.branch:
			existing = frappe.db.get_value(
				"Library Books",
				{"accession_number": self.accession_number, "branch": self.branch},
				"name",
			)
			if existing and existing != self.name:
				frappe.throw(
					_("Accession number {0} already exists for branch {1}").format(
						self.accession_number,
						self.branch,
					)
				)
