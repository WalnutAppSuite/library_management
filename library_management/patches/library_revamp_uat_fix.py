"""Heal the schema/data state on sites that are upgrading to library-revamp.

Specifically:
1. Drop the legacy `avail_quantity` (varchar) column on Library Books — relic
   from a pre-revamp UI-created field that was renamed to `available_quantity`.
2. Reconcile NULL/0 values on `quantity` and `available_quantity` so the
   issue/return code paths don't crash on `cint(None) > 0` and don't refuse
   to issue books that actually have stock.
3. Flip the `Student.custom_library_books` Custom Field to is_virtual=1 so
   the field reads through the LibraryBooksStudentTable.get_list() join
   instead of from a denormalized physical table.
4. Truncate the orphaned `tabLibrary Books Student Table` rows — their data
   is recoverable from the migrated `Library Transaction Book` child rows.
5. Clear the relevant DocType caches so subsequent requests pick up the new
   meta.

Idempotent: safe to run on an already-fixed site.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    drop_legacy_avail_quantity_column()
    reconcile_book_quantities()
    ensure_student_custom_field_is_virtual()
    truncate_orphaned_snapshot_table()
    frappe.clear_cache(doctype="Student")
    frappe.clear_cache(doctype="Library Books")


def drop_legacy_avail_quantity_column():
    """Remove the relic `avail_quantity` varchar column from `tabLibrary Books`."""
    if not frappe.db.table_exists("Library Books"):
        return
    cols = [r[0] for r in frappe.db.sql("SHOW COLUMNS FROM `tabLibrary Books`")]
    if "avail_quantity" in cols:
        frappe.db.sql("ALTER TABLE `tabLibrary Books` DROP COLUMN `avail_quantity`")
        frappe.logger("library_management").info(
            "library_revamp_uat_fix: dropped legacy avail_quantity column"
        )


def reconcile_book_quantities():
    """NULL/0 quantity/available_quantity → sane defaults.

    Per the agreed policy:
      - quantity NULL or 0 → 1
      - available_quantity NULL or 0 → quantity (after the line above runs)
    Books actively borrowed will have available_quantity reduced by the issue
    flow when needed; this only fixes the "broken/uninitialized" state.
    """
    if not frappe.db.table_exists("Library Books"):
        return

    fixed_quantity = frappe.db.sql(
        "UPDATE `tabLibrary Books` SET quantity=1 WHERE quantity IS NULL OR quantity=0"
    )
    fixed_available = frappe.db.sql(
        "UPDATE `tabLibrary Books` SET available_quantity=quantity "
        "WHERE available_quantity IS NULL OR available_quantity=0"
    )
    frappe.logger("library_management").info(
        "library_revamp_uat_fix: quantity reset on rows; available_quantity reconciled"
    )


def ensure_student_custom_field_is_virtual():
    """Ensure Student.custom_library_books exists and is wired to the
    Library Books Student Table.

    Frappe v15 enforces `parent_doctype.is_virtual == child_doctype.is_virtual`
    on Table fields (`frappe/core/doctype/doctype/doctype.py:check_child_table_option`),
    which means a regular Student doctype CANNOT have a virtual child
    table here, even though we want virtual-like behavior.

    Workaround:
    - Library Books Student Table is_virtual=0 (regular child table).
    - Custom Field is_virtual=0 (matches parent).
    - Frappe still auto-fetches rows from the physical
      tabLibrary Books Student Table on parent load — which after the
      truncate below is empty.
    - The Student.onload doc_event then populates the field with rows
      from the join over Library Transaction Book ↔ Library Transactions
      filtered by student. So users see live data on every form open.
    - Saved rows on the parent become a stale cache; harmless because
      onload overwrites them on the next open.

    Existing sites that previously had is_virtual=1 set get the flag
    flipped here (direct DB update bypasses Frappe's `check_child_table_option`
    which would refuse the change).

    Idempotent.
    """
    if not frappe.db.exists("DocType", "Student"):
        return
    if not frappe.db.exists("DocType", "Library Books Student Table"):
        return

    # Flip the child doctype's is_virtual to 0 if it's still 1 from an
    # earlier deploy. Direct DB update — Frappe's validate would refuse.
    if frappe.db.get_value("DocType", "Library Books Student Table", "is_virtual") == 1:
        frappe.db.set_value(
            "DocType", "Library Books Student Table", "is_virtual", 0,
            update_modified=False,
        )
        frappe.logger("library_management").info(
            "library_revamp_uat_fix: flipped Library Books Student Table.is_virtual to 0"
        )

    create_custom_fields(
        {
            "Student": [
                {
                    "fieldname": "custom_library_books",
                    "label": "Library Books",
                    "fieldtype": "Table",
                    "options": "Library Books Student Table",
                    "is_virtual": 0,
                    "no_copy": 1,
                    "print_hide": 1,
                    "insert_after": "custom_number_of_books_issued",
                }
            ]
        },
        update=True,
    )

    # Existing edu_quality definitions had is_virtual=1; flip back to 0
    # via direct DB update (validate path would otherwise reject).
    cf_name = frappe.db.exists(
        "Custom Field",
        {"dt": "Student", "fieldname": "custom_library_books"},
    )
    if cf_name and frappe.db.get_value("Custom Field", cf_name, "is_virtual") != 0:
        frappe.db.set_value(
            "Custom Field", cf_name, "is_virtual", 0,
            update_modified=False,
        )


def truncate_orphaned_snapshot_table():
    """Drop the denormalized Library Books Student Table rows.

    They were written by the old single-book flow as snapshots on Student.
    The same data is now reachable by joining Library Transaction Book ↔
    Library Transactions filtered by student (the virtual get_list query).
    """
    if frappe.db.table_exists("Library Books Student Table"):
        before = frappe.db.count("Library Books Student Table")
        frappe.db.sql("TRUNCATE `tabLibrary Books Student Table`")
        frappe.logger("library_management").info(
            f"library_revamp_uat_fix: truncated {before} stale Library Books Student Table rows"
        )
