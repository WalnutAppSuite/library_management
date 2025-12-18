// Copyright (c) 2025, Frappe and contributors
// For license information, please see license.txt



console.log("Library Transactions JS loaded");
frappe.ui.form.on("Library Transactions", {
    // Add flag to prevent double triggering
    _is_fetching_book_details: false,
    
    refresh(frm) {
        // Set field properties
        set_field_properties(frm);
        
        // Auto-calculate due days on refresh
        calculate_due_days(frm);
    },
    
    // Auto-populate student details when student is selected
    student(frm) {
        if (frm.doc.student) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Student",
                    fieldname: ["user", "program", "school"],
                    filters: { name: frm.doc.student }
                },
                callback: function(r) {
                    if (r.message) {
                        // Auto-fill student details
                        frm.set_value("student_email", r.message.user || "");
                        frm.set_value("classs", r.message.program || "");
                        frm.set_value("branch", r.message.school || "");
                        
                    } else {
                        frappe.msgprint({
                            message: __("Could not fetch student details. Please check the student record."),
                            indicator: "orange"
                        });
                    }
                },
                error: function(err) {
                    frappe.msgprint({
                        message: __("Error fetching student details: ") + (err.message || "Unknown error"),
                        indicator: "red"
                    });
                }
            });
        } else {
            // Clear dependent fields when student is cleared
            frm.set_value("student_email", "");
            frm.set_value("classs", "");
            frm.set_value("branch", "");
        }
    },
    
    // Auto-populate book details when ISBN is entered
    isbn(frm) {
        // Prevent double triggering
        if (frm._is_fetching_book_details) {
            return;
        }
        
        if (frm.doc.isbn && frm.doc.isbn.trim()) {
            frm._is_fetching_book_details = true;
            fetch_book_details_by_field(frm, "isbn", frm.doc.isbn.trim());
        } else {
            clear_book_details(frm);
        }
    },
    
    // Auto-populate book details when Accession Number is entered
    accession_number(frm) {
        // Prevent double triggering
        if (frm._is_fetching_book_details) {
            return;
        }
        
        if (frm.doc.accession_number && frm.doc.accession_number.trim()) {
            frm._is_fetching_book_details = true;
            fetch_book_details_by_field(frm, "accession_number", frm.doc.accession_number.trim());
        } else if (!frm.doc.isbn) {
            // Only clear if ISBN is also not present
            clear_book_details(frm);
        }
    },
    
    // Auto-calculate reading period when dates change
    date_of_issue(frm) {
        calculate_reading_period(frm);
    },
    
    return_date(frm) {
        calculate_reading_period(frm);
        calculate_due_days(frm);
    },
    
    book_status(frm) {
            if (frm.doc.book_status === "RENEWED") {
        frm.set_value("return_date", frappe.datetime.now_datetime());
    }

        calculate_due_days(frm); 
        if (frm.doc.book_status === "RENEWED") {
            frm.set_df_property("return_date", "read_only", 1);
        } else {
            frm.set_df_property("return_date", "read_only", 0);
        }


        if (frm.doc.book_status === "RENEWED") {
    frm.set_value("due_days", "0 days");
    frm.dashboard.clear_headline();}

    },


   

    
    // Validation before save
    before_save(frm) {
        // Validate required fields
        if (!frm.doc.student) {
            frappe.msgprint(__("Please select a student"));
            frappe.validated = false;
            return;
        }
        
        if (!frm.doc.isbn && !frm.doc.accession_number) {
            frappe.msgprint(__("Please enter either ISBN or Accession Number"));
            frappe.validated = false;
            return;
        }
        
        if (!frm.doc.book_name) {
            frappe.msgprint(__("Book details not found. Please check ISBN or Accession Number"));
            frappe.validated = false;
            return;
        }
        
        // Validate take_home permission
        if (!frm.doc.take_home) {
            frappe.msgprint(__("This book is not allowed for home reading. Only books with 'Take Home' permission can be issued."));
            frappe.validated = false;
            return;
        }
        
        // Validate dates
        if (frm.doc.date_of_issue && frm.doc.return_date) {
            if (frm.doc.return_date < frm.doc.date_of_issue) {
                frappe.msgprint(__("Return date cannot be before issue date"));
                frappe.validated = false;
                return;
            }
        }
        
        // Check quantity
        if (frm.doc.quantity_available <= 0 && frm.doc.book_status === "READING") {
            frappe.confirm(
                __("This book is out of stock. Do you still want to proceed?"),
                function() {
                    // Continue with save
                },
                function() {
                    frappe.validated = false;
                }
            );
        }
    }
});

// Helper function to fetch book details by field (ISBN or Accession Number)
function fetch_book_details_by_field(frm, field_name, field_value) {
    if (!field_value) {
        frm._is_fetching_book_details = false;
        return;
    }
    
    // Show loading indicator
    frm.dashboard.set_headline_alert("Fetching book details...", "blue");
    
    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "Library Books",
            fieldname: [
                "book_name", 
                "author", 
                "publisher", 
                "available_quantity", 
                "take_home", 
                "branch",
                "isbn",
                "accession_number",
                "status"
            ],
            filters: { [field_name]: field_value }
        },
        callback: function(r) {
            // Clear loading indicator
            frm.dashboard.clear_headline();
            
            if (r.message) {
                let book = r.message;
                
                // Check if book is active
                if (book.status !== "Active") {
                    frappe.msgprint({
                        message: __("Warning: This book is not active in the system"),
                        indicator: "orange"
                    });
                }
                
                // Auto-fill book details
                frm.set_value("book_name", book.book_name || "");
                frm.set_value("author", book.author || "");
                frm.set_value("publisher", book.publisher || "");
                frm.set_value("quantity_available", book.available_quantity || 0);
                frm.set_value("take_home", book.take_home || 0);
                
                // Cross-populate ISBN and Accession Number WITHOUT triggering field events
                if (field_name === "isbn" && book.accession_number && !frm.doc.accession_number) {
                    frm.doc.accession_number = book.accession_number;
                    frm.refresh_field("accession_number");
                } else if (field_name === "accession_number" && book.isbn && !frm.doc.isbn) {
                    frm.doc.isbn = book.isbn;
                    frm.refresh_field("isbn");
                }
                
                // Auto-set dates and calculate reading period
                if (!frm.doc.date_of_issue) {
                    frm.set_value("date_of_issue", frappe.datetime.get_today());
                }
                
                if (!frm.doc.return_date) {
                    // Set return date to 7 days from today
                    let return_date = frappe.datetime.add_days(frappe.datetime.get_today(), 7);
                    frm.set_value("return_date", return_date);
                }
                
                // Calculate reading period after setting dates
                setTimeout(function() {
                    calculate_reading_period(frm);
                }, 100);
                
                // Check take_home permission
                if (!book.take_home) {
                    frappe.msgprint({
                        message: __("Warning: This book is not allowed for home reading"),
                        indicator: "red"
                    });
                    frm.dashboard.set_headline_alert("Book Not Available for Home Reading", "red");
                }
                
                // Check availability
                if (book.available_quantity <= 0) {
                    frappe.msgprint({
                        message: __("Warning: This book is currently out of stock"),
                        indicator: "red"
                    });
                    frm.dashboard.set_headline_alert("Book Out of Stock", "red");
                } else if (book.available_quantity <= 2) {
                    frappe.msgprint({
                        message: __("Notice: Only {0} copies available", [book.available_quantity]),
                        indicator: "orange"
                    });
                }
                
                // Update branch if different from student's branch
                if (book.branch && frm.doc.branch && book.branch !== frm.doc.branch) {
                    frappe.msgprint({
                        message: __("Note: Book belongs to {0} branch, but student is from {1} branch", 
                                  [book.branch, frm.doc.branch]),
                        indicator: "yellow"
                    });
                }
                
                // Success message
                frappe.msgprint({
                    message: __("Book details populated successfully"),
                    indicator: "green"
                });
                
            } else {
                // Book not found
                frappe.msgprint({
                    message: __("No book found with {0}: {1}", [field_name.replace("_", " "), field_value]),
                    indicator: "red"
                });
                
                // Clear book details if not found
                clear_book_details(frm, false);
            }
            
            // Reset the flag after processing is complete
            frm._is_fetching_book_details = false;
        },
        error: function(err) {
            frm.dashboard.clear_headline();
            frappe.msgprint({
                message: __("Error fetching book details: ") + (err.message || "Unknown error"),
                indicator: "red"
            });
            
            // Reset the flag on error
            frm._is_fetching_book_details = false;
        }
    });
}

// Helper function to clear book details
function clear_book_details(frm, clear_identifiers = true) {
    frm.set_value("book_name", "");
    frm.set_value("author", "");
    frm.set_value("publisher", "");
    frm.set_value("quantity_available", "");
    frm.set_value("take_home", 0);
    frm.set_value("date_of_issue", "");
    frm.set_value("return_date", "");
    frm.set_value("reading_period", "");
    frm.set_value("due_days", "");
    
    if (clear_identifiers) {
        frm.set_value("isbn", "");
        frm.set_value("accession_number", "");
    }
    
    frm.dashboard.clear_headline();
}

// Helper function to calculate reading period
function calculate_reading_period(frm) {
    if (frm.doc.date_of_issue && frm.doc.return_date) {
        let issue_date = frappe.datetime.str_to_obj(frm.doc.date_of_issue);
        let return_date = frappe.datetime.str_to_obj(frm.doc.return_date);
        let days = frappe.datetime.get_diff(return_date, issue_date);
        
        if (days >= 0) {
            frm.set_value("reading_period", days + " days");
        } else {
            frappe.msgprint({
                message: __("Return date cannot be before issue date"),
                indicator: "red"
            });
        }
    }
}

// Helper function to calculate due days
function calculate_due_days(frm) {
    if (frm.doc.book_status === "READING" && frm.doc.return_date) {
        let today = frappe.datetime.get_today();
        let return_date = frm.doc.return_date;
        
        if (today > return_date) {
            let overdue_days = frappe.datetime.get_diff(today, return_date);
            frm.set_value("due_days", overdue_days + " days");
            
            // Show overdue warning
            frm.dashboard.set_headline_alert(`Book Overdue by ${overdue_days} days`, "red");
        } else {
            frm.set_value("due_days", "0 days");
            if (frm.doc.book_status === "READING") {
                frm.dashboard.clear_headline();
            }
        }
    } else {
        frm.set_value("due_days", "0 days");
    }
}

// Child table event handler for Library Books Student Table
frappe.ui.form.on("Library Books Student Table", {
    book_status: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.book_status === "RENEWED") {
            // Set book_return_date to current date and time when RENEWED is selected
            frappe.model.set_value(cdt, cdn, "book_return_date", frappe.datetime.now_datetime());
        }
    }
});

// Helper function to set field properties
function set_field_properties(frm) {
    // Make certain fields read-only after book details are populated
    if (frm.doc.book_name) {
        frm.set_df_property("book_name", "read_only", 1);
        frm.set_df_property("author", "read_only", 1);
        frm.set_df_property("publisher", "read_only", 1);
        frm.set_df_property("quantity_available", "read_only", 1);
    }

    // Set field descriptions
    frm.set_df_property("isbn", "description", "Enter ISBN to auto-populate book details");
    frm.set_df_property("accession_number", "description", "Enter Accession Number to auto-populate book details");

    // Highlight take_home field if not checked
    if (frm.doc.take_home === 0 && frm.doc.book_name) {
        frm.set_df_property("take_home", "description", "⚠️ This book is not allowed for home reading");
    }
}