# Copyright (c) 2025, Frappe and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from library_management.services import is_valid_isbn, normalize_isbn


class TestLibraryBooks(FrappeTestCase):
	def test_isbn_normalization_and_validation(self):
		self.assertEqual(normalize_isbn("978-0-306-40615-7"), "9780306406157")
		self.assertTrue(is_valid_isbn("9780306406157"))
		self.assertTrue(is_valid_isbn("0-306-40615-2"))
		self.assertFalse(is_valid_isbn("9780306406158"))
