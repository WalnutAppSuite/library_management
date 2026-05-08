"""Drop the upstream Frappe demo doctypes that aren't used by the new flow.

The new flow uses:
- Library Books         (replaces Article)
- Student               (replaces Library Member; lives in education/edu_quality)
- Library Transactions  (replaces single-book Library Transaction)
- Library Transaction Book (multi-book child rows)

These are dead and conflict with education's own `Article` doctype:
- Library Transaction (singular)
- Article
- Library Member
- Library Membership

Idempotent: skips doctypes that are already gone.
"""
import frappe


LEGACY_DOCTYPES = [
    "Library Transaction",
    "Article",
    "Library Member",
    "Library Membership",
]


def execute():
    for name in LEGACY_DOCTYPES:
        try:
            # Education app also has an "Article" DocType. If education's row
            # has supplanted library_management's (e.g. after re-sync),
            # leave it alone — only drop when this row still belongs to us.
            if frappe.db.exists("DocType", name):
                module = frappe.db.get_value("DocType", name, "module")
                if name == "Article" and module != "Library Management":
                    continue
                frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
                frappe.logger("library_management").info(
                    f"drop_legacy_doctypes: dropped DocType {name!r} (module={module})"
                )

            # frappe.delete_doc(DocType, ..., force=True) does NOT drop the
            # underlying tab table — do that explicitly.
            if frappe.db.sql(f"SHOW TABLES LIKE 'tab{name}'"):
                frappe.db.sql(f"DROP TABLE `tab{name}`")
                frappe.logger("library_management").info(
                    f"drop_legacy_doctypes: dropped table tab{name}"
                )
        except Exception:
            frappe.log_error(
                title="drop_legacy_doctypes",
                message=f"Failed to drop {name!r}\n{frappe.get_traceback()}",
            )
