"""after_migrate hook — runs every `bench migrate`.

Defends against another app (e.g. edu_quality) re-asserting
`Student.custom_library_books.is_virtual = 0` from a stale customization
fixture. Library_management owns this field; if anyone changes the
flag, we put it back. Idempotent.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
    try:
        _run_after_migrate()
    except Exception:
        frappe.db.rollback()
        _run_after_migrate()
        frappe.db.commit()


def _run_after_migrate():
    if not frappe.db.exists("DocType", "Student"):
        return
    if not frappe.db.exists("DocType", "Library Books Student Table"):
        return

    # Frappe v15 enforces parent_doctype.is_virtual == child.is_virtual on
    # Table fields. Student is regular (0), so the child doctype must also
    # be 0. Flip back if anyone re-stomped is_virtual to 1.
    if frappe.db.get_value("DocType", "Library Books Student Table", "is_virtual") == 1:
        frappe.db.set_value(
            "DocType", "Library Books Student Table", "is_virtual", 0,
            update_modified=False,
        )

    # Self-ship the per-student issued counter on Education-only sites. Where
    # another app (e.g. edu_quality) already defines it, leave that definition
    # untouched — create only when missing so we never alter an existing
    # field's type or position on a shared site.
    if not frappe.db.exists(
        "Custom Field", {"dt": "Student", "fieldname": "custom_number_of_books_issued"}
    ):
        create_custom_fields(
            {
                "Student": [
                    {
                        "fieldname": "custom_number_of_books_issued",
                        "label": "Number of Books Issued",
                        "fieldtype": "Data",
                        "read_only": 1,
                        "no_copy": 1,
                        "insert_after": "image",
                    }
                ]
            },
            update=False,
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

    cf_name = frappe.db.exists(
        "Custom Field",
        {"dt": "Student", "fieldname": "custom_library_books"},
    )
    if cf_name and frappe.db.get_value("Custom Field", cf_name, "is_virtual") != 0:
        frappe.db.set_value(
            "Custom Field", cf_name, "is_virtual", 0,
            update_modified=False,
        )

    frappe.clear_cache(doctype="Student")
