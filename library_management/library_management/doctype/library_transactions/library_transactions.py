# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LibraryTransactions(Document):
	pass

'''
# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

class LibraryTransactions(Document):
    def on_update(self):
        update_period_and_due_days(self, 'on_update')

    def on_submit(self):
        update_period_and_due_days(self, 'on_submit')

    def on_change(self):
        if self.isbn or self.accession_number:
            fetch_book_details(self, 'on_change')

    def after_save(self):
        validate_library_transaction(self, 'after_save')


# Function to update the reading_period and due_days
def update_period_and_due_days(doc, method):
    date_of_issue = doc.date_of_issue
    return_date = doc.return_date
    book_status = doc.book_status

    if date_of_issue and return_date:
        # Calculate the difference in days between return date and issue date
        days_difference = getdate(return_date) - getdate(date_of_issue)
        doc.reading_period = f"{days_difference.days + 1} days"  # Include both start and end date

    if book_status == 'READING' and return_date:
        today = getdate()
        days_since_return = today - getdate(return_date)
        doc.due_days = f"{max(days_since_return.days + 1, 0)} days"  # Calculate due days

    doc.save()


# Function to fetch book details from Library Books based on ISBN or Accession Number
def fetch_book_details(doc, method):
    # Fetch data from Library Books based on ISBN or Accession Number
    if doc.isbn:
        filters = {'isbn': doc.isbn}
    elif doc.accession_number:
        filters = {'accession_number': doc.accession_number}
    else:
        return

    book = frappe.get_all('Library Books', filters=filters, fields=["book_name", "accession_number", "author", "publisher", "avail_quantity", "take_home", "branch"])

    if book:
        book = book[0]  # Fetch the first result
        doc.book_name = book.get("book_name")
        doc.accession_number = book.get("accession_number")
        doc.quantity_available = book.get("avail_quantity")
        doc.author = book.get("author")
        doc.publisher = book.get("publisher")
        doc.take_home = book.get("take_home")
        doc.branch = book.get("branch")
        doc.save()
    else:
        frappe.msgprint(__('No matching book found for the provided ISBN or Accession Number.'))


# Function to validate library transaction (book issuance)
def validate_library_transaction(doc, method):
    reference_number = doc.student_ref
    class_name = doc.classs
    student_name = doc.student
    isbn = doc.isbn
    accession_number = doc.accession_number

    if reference_number and class_name and student_name and (isbn or accession_number):
        # Fetch all library transactions except the current document
        all_library_transactions = frappe.get_all('Library Transactions',
                                                  filters={
                                                      'classs': class_name,
                                                      'student_ref': reference_number,
                                                      'isbn': isbn,
                                                      'student': student_name,
                                                      'book_status': doc.book_status,
                                                      'return_date': doc.return_date,
                                                      'name': ('!=', doc.name)
                                                  })

        if all_library_transactions:
            frappe.throw("Same book cannot be taken repeatedly at a time.")

        # Fetch Program Enrollment document for the student and class
        program_enrollment = frappe.get_doc("Program Enrollment", {"student": student_name, "program": class_name})
        if program_enrollment:
            if program_enrollment.custom_library_membership:
                student_doc = frappe.get_doc("Student", {"reference_number": reference_number, "program": class_name})
                if student_doc:
                    # Count the number of books issued by reference_number
                    issued_books_count = frappe.db.count("Library Transactions",
                                                         filters={"student_ref": reference_number,
                                                                  "classs": class_name,
                                                                  "book_status": ("!=", "RETURNED")})
                    if issued_books_count > 2:
                        frappe.throw("Only three books are allowed to be issued at a time.")

                    # Update custom_number_of_books_issued with the count of issued books
                    student_doc.custom_number_of_books_issued = issued_books_count

                    # Fetch library details for the student
                    library_details = frappe.get_all("Library Transactions",
                                                     filters={"student_ref": reference_number, "classs": class_name},
                                                     fields=["book_name", "author", "date_of_issue", "return_date", "take_home",
                                                             "reading_period", "due_days", "book_status"])

                    if library_details:
                        student_doc.set("custom_books", [])
                        update = False
                        for detail in library_details:
                            if detail.get("take_home") == 1:
                                # Use ISBN or accession_number to fetch book details
                                book_filters = {"isbn": isbn} if isbn else {"accession_number": accession_number}
                                book_details = frappe.get_all("Library Books", filters=book_filters,
                                                              fields=["name", "book_name", "avail_quantity", "author", "publisher", "take_home"],
                                                              limit_page_length=1)

                                if book_details:
                                    book_details = book_details[0]  # Get the first result
                                    current_quantity = int(book_details.get('avail_quantity', 0) or 0)
                                    if doc.book_status == "READING":
                                        if current_quantity < 0:
                                            frappe.throw("Book is out of stock.")
                                        if not update:
                                            book_details['avail_quantity'] = current_quantity - 1
                                            update = True
                                    elif doc.book_status == "RETURNED":
                                        if not update:
                                            book_details['avail_quantity'] = current_quantity + 1
                                            frappe.msgprint("Book quantity updated")
                                            update = True

                                    frappe.get_doc("Library Books", book_details['name']).update({"avail_quantity": book_details['avail_quantity']}).save()

                                # Append book details to custom_books
                                library_book = student_doc.append("custom_library_books", {})
                                library_book.book_name = book_details['book_name']
                                library_book.author = detail.get("author")
                                library_book.date_of_issue = detail.get("date_of_issue")
                                library_book.return_date = detail.get("return_date")
                                library_book.take_home = detail.get("take_home")
                                library_book.reading_period = detail.get("reading_period")
                                library_book.due_days = detail.get("due_days")
                                library_book.book_status = detail.get("book_status")

                        student_doc.save()
                        frappe.msgprint("Library book details updated in Student document.")
                else:
                    frappe.throw("Student document not found for the given reference number.")
            else:
                frappe.throw("Student is not allowed to issue library books.")
        else:
            frappe.throw("Program Enrollment not found for the student and class.")
    else:
        frappe.throw("Reference number, class, student, or book details not found in the newly added Library Transaction record.")'''
