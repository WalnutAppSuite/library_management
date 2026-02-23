# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days, date_diff, cint
from frappe import _
from frappe.utils import now_datetime
class LibraryTransactions(Document):
    def validate(self):
        """Validate document before saving"""
        self.validate_required_fields()
        self.validate_take_home_permission()
        self.validate_student_details()
        self.validate_book_details()
        self.validate_stock_availability()
        self.validate_dates()
        self.auto_set_dates()
        self.set_renewed_datetime()   
        self.calculate_reading_period()
        self.calculate_due_days()
    def after_insert(self):
        """After inserting the document - only for new records"""
        if self.book_status == "READING":
            self.update_student_library_books()
            self.update_book_inventory()
    def on_update_after_submit(self):
        """After updating submitted document"""
        # Only update if this is a status change
        if self.has_value_changed("book_status"):
            self.update_student_library_books()
    def on_update(self):
        """On document update - handle status changes"""
        # Only update for existing records and if status changed
        if not self.is_new() and self.has_value_changed("book_status"):
            self.update_student_library_books()
    def validate_required_fields(self):
        """Validate required fields"""
        if not self.student:
            frappe.throw(_("Student is required"))
        if not self.isbn and not self.accession_number:
            frappe.throw(_("Either ISBN or Accession Number is required"))
    def validate_take_home_permission(self):
        """Validate if book is allowed for home reading"""
        if not self.take_home and self.book_status == "READING":
            frappe.throw(_("This book is not allowed for home reading. Only books with 'Take Home' permission can be issued."))
    def auto_set_dates(self):
        """Auto-set dates if not provided"""
        if not self.date_of_issue:
            self.date_of_issue = today()
        if not self.return_date and self.date_of_issue:
            self.return_date = add_days(self.date_of_issue, 7)
    def validate_student_details(self):
        """Validate and auto-populate student details"""
        if self.student:
            student = frappe.get_value("Student", self.student, 
                                     ["user", "program", "school", "reference_number"], as_dict=True)
            if student:
                if not self.student_email:
                    self.student_email = student.user
                if not self.classs:
                    self.classs = student.program
                if not self.branch:
                    self.branch = student.school
    def validate_book_details(self):
        """Validate and auto-populate book details"""
        if (self.isbn or self.accession_number) and not self.book_name:
            search_field = "isbn" if self.isbn else "accession_number"
            search_value = self.isbn if self.isbn else self.accession_number
            book = frappe.get_value("Library Books", 
                                  {search_field: search_value},
                                  ["book_name", "author", "publisher", "available_quantity", 
                                   "take_home", "branch", "isbn", "accession_number", "status"],
                                  as_dict=True)
            if book:
                if book.status != "Active":
                    frappe.msgprint(_("Warning: This book is not active in the system"))
                self.book_name = book.book_name
                self.author = book.author
                self.publisher = book.publisher
                self.quantity_available = book.available_quantity
                self.take_home = book.take_home
                if search_field == "isbn" and book.accession_number and not self.accession_number:
                    self.accession_number = book.accession_number
                elif search_field == "accession_number" and book.isbn and not self.isbn:
                    self.isbn = book.isbn
                if cint(book.available_quantity) <= 0:
                    frappe.msgprint(_("Warning: This book is currently out of stock"))
            else:
                frappe.throw(_("No book found with {0}: {1}")
                           .format(search_field.replace("_", " "), search_value))
    def validate_stock_availability(self):
        """Validate stock availability for book issuance"""
        if self.book_status == "READING" and (self.isbn or self.accession_number):
            search_field = "isbn" if self.isbn else "accession_number"
            search_value = self.isbn if self.isbn else self.accession_number
            current_stock = frappe.get_value("Library Books", 
                                           {search_field: search_value}, 
                                           "available_quantity")
            if current_stock is not None and cint(current_stock) <= 0:
                frappe.throw(_("Cannot issue this book. Current available quantity is {0}. Please check book inventory.").format(current_stock))
    def validate_dates(self):
        """Validate date fields"""
        if self.date_of_issue and self.return_date:
            if getdate(self.return_date) < getdate(self.date_of_issue):
                frappe.throw(_("Return date cannot be before issue date"))
    def calculate_reading_period(self):
        """Calculate reading period based on issue and return dates"""
        if self.date_of_issue and self.return_date:
            days = date_diff(self.return_date, self.date_of_issue)
            self.reading_period = f"{days} days"
    def calculate_due_days(self):
        """Calculate overdue days if applicable"""
        if (self.book_status == "READING" and 
            self.return_date and 
            getdate(self.return_date) < getdate(today())):
            overdue_days = date_diff(today(), self.return_date)
            self.due_days = f"{overdue_days} days"
        else:
            self.due_days = "0 days"
    def update_student_library_books(self):
        """Update student's custom_library_books child table"""
        if not self.student or not self.book_name:
            return
        # Add flag to prevent multiple calls in same request
        if hasattr(frappe.local, 'library_update_processed') and frappe.local.library_update_processed:
            return
        try:
            student_doc = frappe.get_doc("Student", self.student)
            # Create unique identifier for this book transaction
            book_identifier = f"{self.book_name}_{self.date_of_issue}_{self.isbn or self.accession_number}"
            # Find existing entry by checking multiple criteria
            existing_entry = None
            for book in student_doc.custom_library_books:
                existing_identifier = f"{book.book_name}_{book.book_issue_date}_{book.book_id}"
                if existing_identifier == book_identifier:
                    existing_entry = book
                    break
            update_made = False
            if existing_entry:
                # Update existing entry
                existing_entry.book_return_date = str(self.return_date) if self.return_date else ""
                existing_entry.reading_period = self.reading_period or ""
                existing_entry.book_status = self.book_status or "READING"
                existing_entry.due__days = self.due_days or "0 days"
                existing_entry.take_home = self.take_home or 0
                existing_entry.author = self.author or ""
                update_made = True
                action_message = _("Updated existing book entry in student record")
            else:
                # Add new entry only if book status is READING (new issue)
                if self.book_status == "READING":
                    library_book = student_doc.append("custom_library_books", {})
                    library_book.book_id = self.isbn or self.accession_number or ""
                    library_book.book_name = self.book_name or ""
                    library_book.reference_number = self.accession_number or ""
                    library_book.book_issue_date = str(self.date_of_issue) if self.date_of_issue else str(today())
                    library_book.book_return_date = str(self.return_date) if self.return_date else ""
                    library_book.reading_period = self.reading_period or ""
                    library_book.book_status = self.book_status or "READING"
                    library_book.take_home = self.take_home or 0
                    library_book.due__days = self.due_days or "0 days"
                    library_book.author = self.author or ""
                    update_made = True
                    action_message = _("Added new book entry to student record")
            if update_made:
                # Update number of books issued - COUNT ONLY READING STATUS BOOKS
                reading_books_count = 0
                for book in student_doc.custom_library_books:
                    if book.book_status == "READING":
                        reading_books_count += 1
                student_doc.number_of_books_issued = str(reading_books_count)
                # Save student document
                student_doc.save(ignore_permissions=True)
                # Show single consolidated message
                frappe.msgprint(_("{0}. Current reading books: {1}").format(action_message, reading_books_count))
                # Set flag to prevent duplicate calls
                frappe.local.library_update_processed = True
        except Exception as e:
            frappe.log_error(f"Error updating student library books: {str(e)}")
            frappe.msgprint(_("Warning: Could not update student library records"))
    def update_book_inventory(self):
        """Update book inventory when book is issued"""
        if (self.book_status == "READING" and 
            (self.isbn or self.accession_number) and
            self.is_new()):
            search_field = "isbn" if self.isbn else "accession_number"
            search_value = self.isbn if self.isbn else self.accession_number
            try:
                book_doc = frappe.get_doc("Library Books", {search_field: search_value})
                if book_doc and book_doc.available_quantity > 0:
                    book_doc.available_quantity -= 1
                    book_doc.save(ignore_permissions=True)
                    frappe.msgprint(_("Book inventory updated - Available quantity: {0}").format(book_doc.available_quantity))  
            except Exception as e:
                frappe.log_error(f"Error updating book inventory: {str(e)}")
    def update_all_due_days():
        """Scheduled function to update due days for all books with status READING"""
        try:
            reading_transactions = frappe.get_all("Library Transactions",filters={"book_status": "READING"},fields=["name", "return_date"])
            for transaction in reading_transactions:
                if transaction.return_date and getdate(transaction.return_date) < getdate(today()):
                    overdue_days = date_diff(today(), transaction.return_date)
                    frappe.db.set_value("Library Transactions", transaction.name,"due_days", f"{overdue_days} days")
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Error in update_all_due_days: {str(e)}")