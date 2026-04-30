frappe.ui.form.on("Library Transactions", {
	refresh(frm) {
		frm.add_custom_button(__("Open Counter"), () => frappe.set_route("library-counter"));
	},

	student(frm) {
		if (!frm.doc.student) {
			return;
		}
		frappe.db.get_value("Student", frm.doc.student, ["user", "program", "school"]).then((r) => {
			const student = r.message || {};
			frm.set_value("student_email", student.user || "");
			frm.set_value("classs", student.program || "");
			frm.set_value("branch", student.school || "");
		});
	},
});

frappe.ui.form.on("Library Transaction Book", {
	library_book(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.library_book) {
			return;
		}
		frappe.db
			.get_value("Library Books", row.library_book, [
				"isbn",
				"accession_number",
				"book_name",
				"author",
				"publisher",
			])
			.then((r) => {
				const book = r.message || {};
				frappe.model.set_value(cdt, cdn, "isbn", book.isbn || "");
				frappe.model.set_value(cdt, cdn, "accession_number", book.accession_number || "");
				frappe.model.set_value(cdt, cdn, "book_name", book.book_name || "");
				frappe.model.set_value(cdt, cdn, "author", book.author || "");
				frappe.model.set_value(cdt, cdn, "publisher", book.publisher || "");
				if (!row.issue_date) {
					frappe.model.set_value(cdt, cdn, "issue_date", frappe.datetime.get_today());
				}
			});
	},

	book_status(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.book_status === "RETURNED" && !row.return_date) {
			frappe.model.set_value(cdt, cdn, "return_date", frappe.datetime.get_today());
		}
	},
});
