"""Heal NULL / 0 / non-numeric (e.g. 'NA') values in tabLibrary Books
quantity and available_quantity columns before Frappe's schema-sync
issues `ALTER ... MODIFY int(11)`.

Without this patch, the ALTER crashes on legacy varchar rows containing
'NA' / blank / NULL with:

    pymysql.err.OperationalError:
    (1292, "Truncated incorrect INTEGER value: 'NA'")

The REGEXP guard never implicitly casts varchar → numeric, so it's safe
on the pre-revamp varchar schema. Idempotent — safe on already-clean
sites (UPDATE matches zero rows).

Policy:
  - quantity NULL / 0 / non-numeric / blank → 1
  - available_quantity NULL / 0 / non-numeric / blank → quantity
"""
import frappe


def execute():
    if not frappe.db.table_exists("Library Books"):
        return

    cols = [r[0] for r in frappe.db.sql("SHOW COLUMNS FROM `tabLibrary Books`")]

    if "quantity" in cols:
        frappe.db.sql(
            """
            UPDATE `tabLibrary Books`
            SET quantity = 1
            WHERE quantity IS NULL
               OR CAST(quantity AS CHAR) NOT REGEXP '^[1-9][0-9]*$'
            """
        )

    if "available_quantity" in cols:
        frappe.db.sql(
            """
            UPDATE `tabLibrary Books`
            SET available_quantity = quantity
            WHERE available_quantity IS NULL
               OR CAST(available_quantity AS CHAR) NOT REGEXP '^[1-9][0-9]*$'
            """
        )
