"""Drop the old `library-book-intake` Page row.

The page was renamed to `add-library-books`. Frappe doesn't auto-remove
the old Page record — it just creates the new one. Without this patch,
both records linger and the old one shows up in user search.

Idempotent: skips if the old row is already gone.
"""
import frappe


def execute():
    if frappe.db.exists("Page", "library-book-intake"):
        try:
            frappe.delete_doc("Page", "library-book-intake", force=True, ignore_missing=True)
            frappe.logger("library_management").info(
                "rename_library_book_intake_page: dropped old Page 'library-book-intake'"
            )
        except Exception:
            frappe.log_error(
                title="rename_library_book_intake_page",
                message=frappe.get_traceback(),
            )
