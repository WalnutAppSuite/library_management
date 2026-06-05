import os

import frappe
from frappe.utils.password import update_password
from library_management import services


def run():
    frappe.set_user("Administrator")

    BRANCH = os.environ.get("DEMO_BRANCH", "Demo Branch")
    ROOM = os.environ.get("DEMO_ROOM", "DEMO-ROOM")
    SHELF = os.environ.get("DEMO_SHELF", "DEMO-01")
    PROGRAM = os.environ.get("DEMO_PROGRAM", "Demo Program")
    CAP_USER = "library-demo@example.com"
    CAP_PASS = "Capture@2026xyz"
    STUDENT = "EDU-DEMO-0001"
    log = []

    # 1) Capture login user (System Manager + Librarian)
    if not frappe.db.exists("User", CAP_USER):
        u = frappe.get_doc({
            "doctype": "User", "email": CAP_USER, "first_name": "Library", "last_name": "Desk",
            "send_welcome_email": 0, "user_type": "System User",
            "roles": [{"role": "System Manager"}, {"role": "Librarian"}],
        })
        u.insert(ignore_permissions=True)
        log.append("created capture user")
    else:
        u = frappe.get_doc("User", CAP_USER)
        have = {r.role for r in u.roles}
        for r in ("System Manager", "Librarian"):
            if r not in have:
                u.append("roles", {"role": r})
        u.enabled = 1
        u.save(ignore_permissions=True)
        log.append("updated capture user")
    update_password(CAP_USER, CAP_PASS)

    # 2) Enable free ISBN lookup so Add Books auto-fill works on camera
    s = frappe.get_single("Library Management Settings")
    s.enable_external_metadata_lookup = 1
    if not s.loan_period:
        s.loan_period = 30
    s.save(ignore_permissions=True)

    # 3) Clean prior demo data (idempotent)
    for tx in frappe.get_all("Library Transactions", filters={"student": STUDENT}):
        frappe.delete_doc("Library Transactions", tx.name, force=True, ignore_permissions=True)
    for b in frappe.get_all("Library Books", filters={"book_shelf": SHELF, "branch": BRANCH}):
        frappe.delete_doc("Library Books", b.name, force=True, ignore_permissions=True)
    frappe.db.sql("DELETE FROM `tabStudent` WHERE name=%s OR reference_number='DEMO001'", STUDENT)

    # 4) Demo books at BRANCH/ROOM/SHELF
    DEMO_BOOKS = [
        ("9780439023481", "The Hunger Games", "Suzanne Collins", "Scholastic"),
        ("9780747532699", "Harry Potter and the Philosopher's Stone", "J. K. Rowling", "Bloomsbury"),
        ("9780545139700", "Harry Potter and the Deathly Hallows", "J. K. Rowling", "Scholastic"),
        ("9780061120084", "To Kill a Mockingbird", "Harper Lee", "Harper Perennial"),
        ("9780451524935", "1984", "George Orwell", "Signet Classics"),
    ]
    acc = int(services.get_next_accession_number(BRANCH))
    books = []
    for isbn, title, author, publisher in DEMO_BOOKS:
        doc = frappe.get_doc({
            "doctype": "Library Books", "isbn": isbn, "book_name": title, "author": author,
            "publisher": publisher, "status": "Active", "branch": BRANCH, "room": ROOM,
            "book_shelf": SHELF, "accession_number": str(acc), "quantity": 1,
            "available_quantity": 1, "take_home": 1,
        })
        doc.insert(ignore_permissions=True)
        services.generate_book_qr(doc.name)
        books.append((doc.name, str(acc)))
        acc += 1
    log.append("created %d demo books, accession %s..%s" % (len(books), books[0][1], books[-1][1]))

    # 5) Demo student via direct DB insert (bypass site-specific Student controller hooks)
    frappe.db.sql(
        """
        INSERT INTO `tabStudent`
            (name, creation, modified, owner, modified_by, docstatus, idx,
             first_name, last_name, student_name, reference_number, school, program, enabled)
        VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 0, 0,
             'Demo', 'Student', 'Demo Student', 'DEMO001', %s, %s, 1)
        """,
        (STUDENT, BRANCH, PROGRAM),
    )
    if not frappe.db.exists("Student", STUDENT):
        raise Exception("student insert failed")
    log.append("created student %s (ref DEMO001)" % STUDENT)

    # 6) History: issue 3, return 1, reissue 1 (2 stay active; books 4 & 5 free for live issue)
    services.create_issue_transaction(
        student=STUDENT,
        books=[{"library_book": books[0][0]}, {"library_book": books[1][0]}, {"library_book": books[2][0]}],
        branch=BRANCH,
    )
    services.return_books(student=STUDENT, books=[{"library_book": books[0][0]}])
    services.reissue_books(student=STUDENT, books=[{"library_book": books[1][0]}])
    log.append("issued 3, returned 1, reissued 1")

    frappe.db.commit()
    print("SEED OK")
    for l in log:
        print(" -", l)
    print("CAPTURE_USER", CAP_USER, CAP_PASS)
    print("FREE_BOOK_ACCESSIONS", books[3][1], books[4][1])
    print("BRANCH", BRANCH, "ROOM", ROOM, "SHELF", SHELF, "STUDENT_REF DEMO001")


run()
