# Copyright (c) 2025, Frappe and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from library_management.services import extract_isbn_from_text


class TestLibraryTransactions(FrappeTestCase):
	def test_extract_isbn_from_scanned_text(self):
		self.assertEqual(
			extract_isbn_from_text("Book barcode ISBN 978-0-306-40615-7"),
			"9780306406157",
		)
