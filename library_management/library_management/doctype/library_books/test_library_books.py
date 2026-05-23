# Copyright (c) 2025, Frappe and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from library_management.library_management.doctype.library_books.library_books import (
	LibraryBooks,
)
from library_management.patches.heal_library_books_quantity_strings import (
	execute as run_heal_patch,
)
from library_management.services import is_valid_isbn, normalize_isbn


class TestLibraryBooks(FrappeTestCase):
	def test_isbn_normalization_and_validation(self):
		self.assertEqual(normalize_isbn("978-0-306-40615-7"), "9780306406157")
		self.assertTrue(is_valid_isbn("9780306406157"))
		self.assertTrue(is_valid_isbn("0-306-40615-2"))
		self.assertFalse(is_valid_isbn("9780306406158"))


class _DocStub:
	"""Minimal stand-in for a Library Books document, used to exercise
	`LibraryBooks.validate` in isolation without requiring the full Frappe
	document machinery (which would otherwise need real Branch / School
	link targets and a saved record)."""

	def __init__(self, **fields):
		# `accession_number` left None so the uniqueness branch in
		# validate() is skipped — keeps these tests scoped to the
		# quantity / available_quantity normalisation contract.
		self.quantity = fields.get("quantity")
		self.available_quantity = fields.get("available_quantity")
		self.accession_number = fields.get("accession_number")
		self.branch = fields.get("branch")
		self.name = fields.get("name")


class TestLibraryBooksValidateQuantity(FrappeTestCase):
	"""validate() contract — quantity normalisation.

	Contract:
	  - 0 / None / '' / non-numeric ('NA', 'garbage') → 1
	  - positive int / numeric string → preserved unchanged
	  - negative int / negative numeric string → preserved unchanged
	    (cint returns the negative, which is truthy → bypasses the `or 1`
	    fallback). This is the intended cleanup contract: validate() rescues
	    *uninitialised* data, not values the caller deliberately wrote.
	"""

	def _validate(self, **fields):
		doc = _DocStub(**fields)
		LibraryBooks.validate(doc)
		return doc

	def test_quantity_zero_becomes_one(self):
		doc = self._validate(quantity=0)
		self.assertEqual(doc.quantity, 1)

	def test_quantity_none_becomes_one(self):
		doc = self._validate(quantity=None)
		self.assertEqual(doc.quantity, 1)

	def test_quantity_empty_string_becomes_one(self):
		doc = self._validate(quantity="")
		self.assertEqual(doc.quantity, 1)

	def test_quantity_na_string_becomes_one(self):
		doc = self._validate(quantity="NA")
		self.assertEqual(doc.quantity, 1)

	def test_quantity_garbage_string_becomes_one(self):
		doc = self._validate(quantity="garbage!@#")
		self.assertEqual(doc.quantity, 1)

	def test_quantity_positive_int_preserved(self):
		doc = self._validate(quantity=42)
		self.assertEqual(doc.quantity, 42)

	def test_quantity_positive_numeric_string_preserved(self):
		doc = self._validate(quantity="42")
		self.assertEqual(doc.quantity, 42)

	def test_quantity_negative_preserved(self):
		# Explicit contract documentation: negative values are NOT coerced
		# to 1 because cint(-3) == -3 is truthy. If we want to reject
		# negatives, the predicate has to be `> 0` rather than `or 1`.
		doc = self._validate(quantity=-3)
		self.assertEqual(doc.quantity, -3)


class TestLibraryBooksValidateAvailableQuantity(FrappeTestCase):
	"""validate() contract — available_quantity normalisation.

	**Regression guard:** available_quantity == 0 is a meaningful business
	state ("every copy is currently borrowed") and MUST be preserved.
	Issue / return flows in services.py (lines ~448, 540, 970, 1046) treat
	`available_quantity <= 0` as the "not available" signal. A previous
	revision of this validate() used `cint(av) or quantity` which silently
	rewrote 0 → quantity on every form save and over-issued borrowed books.
	"""

	def _validate(self, **fields):
		doc = _DocStub(**fields)
		LibraryBooks.validate(doc)
		return doc

	def test_available_quantity_zero_preserved_when_fully_borrowed(self):
		# REGRESSION GUARD — see class docstring.
		doc = self._validate(quantity=3, available_quantity=0)
		self.assertEqual(doc.available_quantity, 0)

	def test_available_quantity_none_defaults_to_quantity(self):
		doc = self._validate(quantity=5, available_quantity=None)
		self.assertEqual(doc.available_quantity, 5)

	def test_available_quantity_positive_preserved(self):
		doc = self._validate(quantity=10, available_quantity=7)
		self.assertEqual(doc.available_quantity, 7)

	def test_available_quantity_none_with_zero_quantity_defaults_to_one(self):
		# quantity is normalised first (0 → 1), then av_qty inherits that.
		doc = self._validate(quantity=0, available_quantity=None)
		self.assertEqual(doc.quantity, 1)
		self.assertEqual(doc.available_quantity, 1)


class TestHealLibraryBooksQuantityStrings(FrappeTestCase):
	"""Tests for the pre_model_sync heal patch.

	The patch's job is to scrub `tabLibrary Books.quantity` and
	`available_quantity` of NULL / 0 / non-numeric values *while the
	columns are still varchar* (pre-revamp legacy state), so Frappe's
	subsequent schema-sync `ALTER ... MODIFY int(11)` does not crash with:

	    pymysql.err.OperationalError:
	    (1292, "Truncated incorrect INTEGER value: 'NA'")

	To exercise the patch realistically we have to put the test rows in
	the same varchar state as legacy prod. DDL implicitly commits and is
	not rolled back by the FrappeTestCase transaction wrapper, so column
	type changes are made in setUpClass / tearDownClass and the original
	int(11) NOT NULL DEFAULT 0 shape is restored at the end.
	"""

	ORIGINAL_COLUMN_DEF = "INT(11) NOT NULL DEFAULT 0"
	VARCHAR_COLUMN_DEF = "VARCHAR(140)"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.sql(
			f"ALTER TABLE `tabLibrary Books` MODIFY quantity {cls.VARCHAR_COLUMN_DEF}"
		)
		frappe.db.sql(
			f"ALTER TABLE `tabLibrary Books` MODIFY available_quantity {cls.VARCHAR_COLUMN_DEF}"
		)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		# Heal anything we left behind so the column-type restore doesn't
		# trip 1292 on the same data the patch was designed to fix.
		# Commit between DML and DDL — Frappe's check_implicit_commit
		# refuses to run an ALTER when there are pending writes in the
		# current transaction.
		frappe.db.sql(
			"DELETE FROM `tabLibrary Books` WHERE name LIKE 'TEST-HEAL-%'"
		)
		frappe.db.commit()
		frappe.db.sql(
			f"ALTER TABLE `tabLibrary Books` MODIFY quantity {cls.ORIGINAL_COLUMN_DEF}"
		)
		frappe.db.commit()
		frappe.db.sql(
			f"ALTER TABLE `tabLibrary Books` MODIFY available_quantity {cls.ORIGINAL_COLUMN_DEF}"
		)
		frappe.db.commit()
		super().tearDownClass()

	def tearDown(self):
		frappe.db.sql(
			"DELETE FROM `tabLibrary Books` WHERE name LIKE 'TEST-HEAL-%'"
		)
		frappe.db.commit()

	# -- helpers ----------------------------------------------------------

	def _seed(self, quantity, available_quantity):
		"""Insert one test row directly via SQL, bypassing validate().
		Returns the row's `name`."""
		name = f"TEST-HEAL-{frappe.utils.random_string(10)}"
		frappe.db.sql(
			"""
			INSERT INTO `tabLibrary Books`
				(name, isbn, book_name, accession_number, author,
				 status, branch, quantity, available_quantity,
				 modified, creation, owner, modified_by, docstatus)
			VALUES
				(%s, %s, %s, %s, %s, %s, %s, %s, %s,
				 NOW(), NOW(), 'Administrator', 'Administrator', 0)
			""",
			(
				name,
				"9780000099991",
				"Heal Test Book",
				name,
				"Test Author",
				"Active",
				"TEST-BRANCH",
				quantity,
				available_quantity,
			),
		)
		frappe.db.commit()
		return name

	def _read(self, name):
		row = frappe.db.sql(
			"SELECT quantity, available_quantity FROM `tabLibrary Books` "
			"WHERE name = %s",
			(name,),
			as_dict=True,
		)
		return row[0] if row else None

	# -- quantity coverage ------------------------------------------------

	def test_heals_quantity_na(self):
		name = self._seed(quantity="NA", available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "1")

	def test_heals_quantity_null(self):
		name = self._seed(quantity=None, available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "1")

	def test_heals_quantity_blank(self):
		name = self._seed(quantity="   ", available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "1")

	def test_heals_quantity_zero(self):
		name = self._seed(quantity="0", available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "1")

	def test_heals_quantity_garbage(self):
		name = self._seed(quantity="garbage", available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "1")

	def test_preserves_valid_quantity(self):
		name = self._seed(quantity="42", available_quantity="5")
		run_heal_patch()
		self.assertEqual(str(self._read(name).quantity), "42")

	# -- available_quantity coverage --------------------------------------

	def test_heals_available_quantity_na_to_quantity(self):
		name = self._seed(quantity="7", available_quantity="NA")
		run_heal_patch()
		self.assertEqual(str(self._read(name).available_quantity), "7")

	def test_heals_available_quantity_null_to_quantity(self):
		name = self._seed(quantity="7", available_quantity=None)
		run_heal_patch()
		self.assertEqual(str(self._read(name).available_quantity), "7")

	def test_heals_available_quantity_blank_to_quantity(self):
		name = self._seed(quantity="7", available_quantity="   ")
		run_heal_patch()
		self.assertEqual(str(self._read(name).available_quantity), "7")

	def test_heals_available_quantity_zero_to_quantity(self):
		# When the column is varchar (pre-revamp legacy), '0' is treated as
		# uninitialised and reset to the (also-normalised) quantity.
		# Post-migrate, the column is int and the issue/return flow's
		# semantic 0 ("all borrowed") is preserved by validate(), not by
		# this patch.
		name = self._seed(quantity="7", available_quantity="0")
		run_heal_patch()
		self.assertEqual(str(self._read(name).available_quantity), "7")

	def test_heals_available_quantity_when_quantity_also_dirty(self):
		# The patch normalises quantity first; available_quantity then
		# inherits the normalised value, not the original 'NA'.
		name = self._seed(quantity="NA", available_quantity="NA")
		run_heal_patch()
		row = self._read(name)
		self.assertEqual(str(row.quantity), "1")
		self.assertEqual(str(row.available_quantity), "1")

	# -- idempotency ------------------------------------------------------

	def test_idempotent_on_clean_data(self):
		name = self._seed(quantity="3", available_quantity="2")
		run_heal_patch()
		first = self._read(name)
		run_heal_patch()
		second = self._read(name)
		self.assertEqual(first.quantity, second.quantity)
		self.assertEqual(first.available_quantity, second.available_quantity)
		self.assertEqual(str(second.quantity), "3")
		self.assertEqual(str(second.available_quantity), "2")

	def test_idempotent_after_heal(self):
		name = self._seed(quantity="NA", available_quantity="NA")
		run_heal_patch()
		first = self._read(name)
		run_heal_patch()
		second = self._read(name)
		self.assertEqual(first.quantity, second.quantity)
		self.assertEqual(first.available_quantity, second.available_quantity)
		self.assertEqual(str(second.quantity), "1")
		self.assertEqual(str(second.available_quantity), "1")
