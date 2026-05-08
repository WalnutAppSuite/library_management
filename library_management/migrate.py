"""after_migrate hook — runs every `bench migrate`.

Defends against another app (e.g. edu_quality) re-asserting
`Student.custom_library_books.is_virtual = 0` from a stale customization
fixture. Library_management owns this field; if anyone changes the
flag, we put it back. Idempotent.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    if not frappe.db.exists("DocType", "Student"):
        return
    if not frappe.db.exists("DocType", "Library Books Student Table"):
        return

    create_custom_fields(
        {
            "Student": [
                {
                    "fieldname": "custom_library_books",
                    "label": "Library Books",
                    "fieldtype": "Table",
                    "options": "Library Books Student Table",
                    "is_virtual": 1,
                    "no_copy": 1,
                    "print_hide": 1,
                    "insert_after": "custom_number_of_books_issued",
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Student")
