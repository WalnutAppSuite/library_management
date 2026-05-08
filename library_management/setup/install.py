"""after_install hook — runs once when the app is freshly installed.

On `bench install-app`, Frappe marks patches in patches.txt as already
applied without executing them. So our healing patches never run on a
brand-new site, leaving the schema/data in a half-baked state. Invoke
their execute() directly here. All are idempotent.
"""
import frappe


def after_install():
    from library_management.patches import (
        library_revamp_uat_fix,
        drop_legacy_doctypes,
    )

    library_revamp_uat_fix.execute()
    drop_legacy_doctypes.execute()
    frappe.db.commit()
