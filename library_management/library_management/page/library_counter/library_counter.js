frappe.pages["library-counter"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Library Counter"),
		single_column: true,
	});

	page.add_button(__("Add Books"), () => frappe.set_route("add-library-books"), {
		btn_class: "btn-primary",
		icon: "add",
	});

	const state = {
		branch: "",
		student: null,
		issueBooks: [],
		_fetching: false,
	};

	page.main.html(`
		<div class="library-counter">
			<div class="counter-topbar">
				<div>
					<h2>${__("Library Counter")}</h2>
					<div class="muted">${__("Select a student, add physical book copies, then issue or return.")}</div>
				</div>
				<div id="branch-pill" class="chip">${__("Branch pending")}</div>
			</div>
			<div class="student-panel panel">
				<div id="student-form"></div>
				<div class="actions">
					<button class="btn btn-primary" id="fetch-student">${__("Fetch Student")}</button>
					<button class="btn btn-default" id="clear-counter">${__("Clear")}</button>
				</div>
				<div id="student-card"></div>
			</div>
			<div class="workspace-grid">
				<div class="panel">
					<div class="section-title">${__("Issue Books")}</div>
					<div id="book-form"></div>
					<div class="actions">
						<button class="btn btn-default" id="add-book">${__("Find Book")}</button>
					</div>
					<div class="table-responsive">
						<table class="table counter-table">
							<thead>
								<tr>
									<th>${__("Accession")}</th>
									<th>${__("ISBN")}</th>
									<th>${__("Title")}</th>
									<th>${__("Author")}</th>
									<th>${__("Publisher")}</th>
									<th>${__("Shelf")}</th>
									<th></th>
								</tr>
							</thead>
							<tbody id="issue-rows"></tbody>
						</table>
					</div>
					<div class="empty-note" id="issue-empty">${__("No books added yet.")}</div>
					<div class="actions">
						<button class="btn btn-issue" id="submit-issue">${__("Issue Books")}</button>
					</div>
				</div>
				<div class="panel">
					<div class="section-title">${__("Active Issued Books")}</div>
					<div id="return-list"></div>
					<div class="actions">
						<button class="btn btn-reissue" id="submit-reissue">${__("Reissue Selected")}</button>
						<button class="btn btn-return" id="submit-return">${__("Return Selected")}</button>
					</div>
				</div>
			</div>
			<div class="panel" id="student-history"></div>
		</div>
	`);

	const studentForm = new frappe.ui.FieldGroup({
		parent: page.main.find("#student-form"),
		fields: [
			{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "School", onchange: onBranchChange },
			{ fieldname: "student", label: __("Student"), fieldtype: "Link", options: "Student", onchange: fetchStudentFromLink },
			{ fieldname: "reference_number", label: __("Reference Number"), fieldtype: "Data" },
		],
	});
	studentForm.make();
	studentForm.get_field("reference_number").$input.on("keydown", function (e) {
		if (e.key === "Enter") {
			const val = studentForm.get_value("reference_number");
			if (val) fetchStudent(val);
		}
	});
	studentForm.get_field("student").get_query = () => {
		const branch = studentForm.get_value("branch");
		return branch ? { filters: { school: branch } } : {};
	};

	const bookForm = new frappe.ui.FieldGroup({
		parent: page.main.find("#book-form"),
		fields: [
			{ fieldname: "book_identifier", label: __("ISBN / Accession Number"), fieldtype: "Data" },
		],
	});
	bookForm.make();
	bookForm.get_field("book_identifier").$input.on("keydown", function (e) {
		if (e.key === "Enter") findBook(bookForm.get_value("book_identifier"));
	});

	bootstrap();

	page.main.find("#fetch-student").on("click", () => {
		const identifier = studentForm.get_value("student") || studentForm.get_value("reference_number");
		fetchStudent(identifier);
	});
	page.main.find("#clear-counter").on("click", clearCounter);
	page.main.find("#add-book").on("click", () => findBook(bookForm.get_value("book_identifier")));
	page.main.find("#submit-issue").on("click", submitIssue);
	page.main.find("#submit-return").on("click", submitReturn);
	page.main.find("#submit-reissue").on("click", submitReissue);
	page.main.on("click", ".remove-issue", function () {
		state.issueBooks.splice(Number(this.dataset.index), 1);
		renderIssueBooks();
	});

	async function bootstrap() {
		const r = await frappe.call("library_management.services.get_user_library_branch");
		if (r.message && r.message.branch && !r.message.is_ho) {
			state.branch = r.message.branch;
			studentForm.set_value("branch", state.branch);
			page.main.find("#branch-pill").text(state.branch);
		}
		renderIssueBooks();
		renderReturns();
	}

	function onBranchChange() {
		const branch = studentForm.get_value("branch") || "";
		state.branch = branch;
		page.main.find("#branch-pill").text(branch || __("Branch pending"));
		if (state.student && branch && state.student.school !== branch) {
			state.student = null;
			state.issueBooks = [];
			studentForm.set_value("student", "");
			studentForm.set_value("reference_number", "");
			renderStudent();
			renderIssueBooks();
			renderReturns();
		}
	}

	async function fetchStudentFromLink() {
		const student = studentForm.get_value("student");
		if (student) await fetchStudent(student);
	}

	async function fetchStudent(identifier) {
		if (state._fetching) return;
		const branch = studentForm.get_value("branch");
		if (!identifier) {
			frappe.msgprint(__("Select a student or enter reference number."));
			return;
		}
		state._fetching = true;
		try {
			const r = await frappe.call("library_management.services.resolve_student", { identifier, branch });
			state.student = r.message;
			studentForm.set_value("student", state.student.name);
			studentForm.set_value("reference_number", state.student.reference_number || "");
			state.branch = branch || state.student.school || "";
			if (state.branch) {
				studentForm.set_value("branch", state.branch);
				page.main.find("#branch-pill").text(state.branch);
			}
			renderStudent();
			renderReturns();
		} finally {
			// Keep guard active for 600ms so Frappe's async validate_link callbacks
			// (fired after set_value on the Link field) don't re-trigger fetchStudent.
			setTimeout(() => { state._fetching = false; }, 600);
		}
	}

	function renderStudent() {
		const s = state.student;
		if (!s) {
			page.main.find("#student-card").empty();
			renderHistory();
			return;
		}
		const image = s.image || "/assets/frappe/images/default-avatar.png";
		page.main.find("#student-card").html(`
			<div class="student-card">
				<img class="avatar" src="${escapeHtml(image)}">
				<div>
					<div class="name">${escapeHtml(s.display_name || s.name)}</div>
					<div class="muted">${escapeHtml(s.reference_number || "")} · ${escapeHtml(s.program || "")} · ${escapeHtml(s.user || "")}</div>
					<div class="chips">
						<span class="chip">${__("Issued")}: ${s.issued_count || 0}</span>
						<span class="chip ${s.overdue_count ? "warn" : ""}">${__("Overdue")}: ${s.overdue_count || 0}</span>
						<span class="chip neutral">${escapeHtml(s.school || "")}</span>
					</div>
				</div>
			</div>
		`);
		renderHistory();
	}

	function renderHistory() {
		const rows = (state.student && state.student.history) || [];
		if (!state.student) {
			page.main.find("#student-history").empty();
			return;
		}
		const body = rows
			.map((row) => {
				const returned = row.book_status === "RETURNED";
				const overdue = !returned && row.due__days && row.due__days !== "0 days";
				return `
					<tr class="${returned ? "" : "is-reading"}">
						<td>${escapeHtml(row.book_name || "")}</td>
						<td>${escapeHtml(row.author || "")}</td>
						<td>${escapeHtml(row.reference_number || "")}</td>
						<td>${escapeHtml(row.book_issue_date || "-")}</td>
						<td>${escapeHtml(returned ? row.book_return_date || "-" : "-")}</td>
						<td><span class="chip ${returned ? "neutral" : ""}">${escapeHtml(row.book_status || "")}</span></td>
						<td>${escapeHtml(String(row.reissue_count || 0))}</td>
						<td>${overdue ? `<span class="chip warn">${escapeHtml(row.due__days)}</span>` : "-"}</td>
					</tr>
				`;
			})
			.join("");
		page.main.find("#student-history").html(`
			<div class="section-title">${__("Issue / Return History")}</div>
			<div class="table-responsive">
				<table class="table counter-table">
					<thead>
						<tr>
							<th>${__("Title")}</th>
							<th>${__("Author")}</th>
							<th>${__("Accession")}</th>
							<th>${__("Issued")}</th>
							<th>${__("Returned")}</th>
							<th>${__("Status")}</th>
							<th>${__("Reissued")}</th>
							<th>${__("Overdue")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
			${rows.length ? "" : `<div class="empty-note">${__("No history yet.")}</div>`}
		`);
	}

	async function findBook(identifier) {
		if (!identifier) {
			frappe.msgprint(__("Enter ISBN or accession number."));
			return;
		}
		const r = await frappe.call("library_management.services.resolve_book_matches", {
			identifier,
			branch: studentForm.get_value("branch"),
		});
		const matches = r.message || [];
		if (matches.length === 1 && matches[0].accession_number === identifier && matches[0].can_issue) {
			addIssueBook(matches[0]);
			return;
		}
		showBookSelector(matches);
	}

	function showBookSelector(matches) {
		if (!matches.length) return;
		const dialog = new frappe.ui.Dialog({
			title: __("Select Book Copy"),
			size: "large",
			fields: [{ fieldname: "matches_html", fieldtype: "HTML" }],
		});
		const rows = matches
			.map(
				(book, index) => `
				<tr>
					<td><a href="/app/library-books/${encodeURIComponent(book.name)}" target="_blank">${escapeHtml(book.accession_number || "")}</a></td>
					<td>${escapeHtml(book.book_name || "")}</td>
					<td>${escapeHtml(book.author || "")}</td>
					<td>${escapeHtml(book.publisher || "")}</td>
					<td>
						<div>${escapeHtml(book.branch || __("No Branch"))}</div>
						<div class="text-muted">${escapeHtml(book.book_shelf || "")}</div>
					</td>
					<td><span class="match-badge ${book.can_issue ? "ok" : "blocked"}">${escapeHtml(book.availability_label || "")}</span></td>
					<td>
						<button class="btn btn-xs btn-primary choose-book" data-index="${index}" ${book.can_issue ? "" : "disabled"}>${__("Select")}</button>
						${book.issue_reason ? `<div class="text-muted small">${escapeHtml(book.issue_reason)}</div>` : ""}
					</td>
				</tr>
			`
			)
			.join("");
		dialog.fields_dict.matches_html.$wrapper.html(`
			<div class="table-responsive">
				<table class="table table-bordered">
					<thead>
						<tr>
							<th>${__("Accession")}</th>
							<th>${__("Title")}</th>
							<th>${__("Author")}</th>
							<th>${__("Publisher")}</th>
							<th>${__("Branch / Shelf")}</th>
							<th>${__("Status")}</th>
							<th></th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
		dialog.fields_dict.matches_html.$wrapper.find(".choose-book").on("click", function () {
			addIssueBook(matches[Number(this.dataset.index)]);
			dialog.hide();
		});
		dialog.show();
		setTimeout(() => {
			const el = dialog.fields_dict.matches_html.$wrapper.find(".table-responsive")[0];
			if (el) el.scrollLeft = 0;
		}, 100);
	}

	function addIssueBook(book) {
		if (!book.can_issue) {
			frappe.msgprint(book.issue_reason || __("This book cannot be issued."));
			return;
		}
		if (state.issueBooks.find((row) => row.name === book.name)) {
			frappe.show_alert({ message: __("Book already added"), indicator: "orange" });
			return;
		}
		state.issueBooks.push(book);
		bookForm.set_value("book_identifier", "");
		renderIssueBooks();
	}

	function renderIssueBooks() {
		page.main.find("#issue-rows").html(
			state.issueBooks
				.map(
					(book, index) => `
					<tr>
						<td>${book.name ? `<a href="/app/library-books/${encodeURIComponent(book.name)}" target="_blank">${escapeHtml(book.accession_number || "")}</a>` : escapeHtml(book.accession_number || "")}</td>
						<td>${escapeHtml(book.isbn || "")}</td>
						<td>${escapeHtml(book.book_name || "")}</td>
						<td>${escapeHtml(book.author || "")}</td>
						<td>${escapeHtml(book.publisher || "")}</td>
						<td>${escapeHtml(book.book_shelf || "")}</td>
						<td><button class="btn btn-xs btn-default remove-issue" data-index="${index}">${__("Remove")}</button></td>
					</tr>
				`
				)
				.join("")
		);
		page.main.find("#issue-empty").toggle(!state.issueBooks.length);
	}

	async function submitIssue() {
		if (!state.student) {
			frappe.msgprint(__("Fetch a student first."));
			return;
		}
		if (!state.issueBooks.length) {
			frappe.msgprint(__("Add at least one book."));
			return;
		}
		await frappe.call({
			method: "library_management.services.create_issue_transaction",
			args: {
				student: state.student.name,
				branch: studentForm.get_value("branch"),
				books: state.issueBooks.map((book) => ({ library_book: book.name })),
			},
			freeze: true,
			freeze_message: __("Issuing books"),
		});
		frappe.show_alert({ message: __("Books issued"), indicator: "green" });
		state.issueBooks = [];
		renderIssueBooks();
		await fetchStudent(state.student.name);
	}

	function renderReturns() {
		const books = (state.student && state.student.active_books) || [];
		page.main.find("#return-list").html(
			books
				.map((book) => {
					const acc = escapeHtml(book.accession_number || "");
					const accCell = book.library_book
						? `<a href="/app/library-books/${encodeURIComponent(book.library_book)}" target="_blank">${acc}</a>`
						: acc;
					return `
					<label class="return-card">
						<div>
							<div class="book-title">${escapeHtml(book.book_name || "")}</div>
							<div class="muted">${accCell} · ${__("Due")}: ${escapeHtml(book.due_date || "-")}</div>
						</div>
						<input type="checkbox" class="return-check"
							value="${escapeHtml(book.name || "")}"
							data-library_book="${escapeHtml(book.library_book || "")}"
							data-accession="${acc}">
					</label>
				`;
				})
				.join("") || `<div class="empty-note">${__("No active issued books.")}</div>`
		);
	}

	function collectSelectedReturns() {
		const books = [];
		page.main.find(".return-check:checked").each(function () {
			books.push({
				txn_book: this.value,
				library_book: this.dataset.library_book || undefined,
				accession_number: this.dataset.accession || undefined,
			});
		});
		return books;
	}

	async function submitReturn() {
		if (!state.student) {
			frappe.msgprint(__("Fetch a student first."));
			return;
		}
		const books = collectSelectedReturns();
		if (!books.length) {
			frappe.msgprint(__("Select at least one book to return."));
			return;
		}
		await frappe.call({
			method: "library_management.services.return_books",
			args: { student: state.student.name, books },
			freeze: true,
			freeze_message: __("Returning books"),
		});
		frappe.show_alert({ message: __("Books returned"), indicator: "green" });
		await fetchStudent(state.student.name);
	}

	async function submitReissue() {
		if (!state.student) {
			frappe.msgprint(__("Fetch a student first."));
			return;
		}
		const books = collectSelectedReturns();
		if (!books.length) {
			frappe.msgprint(__("Select at least one book to reissue."));
			return;
		}
		await frappe.call({
			method: "library_management.services.reissue_books",
			args: { student: state.student.name, books },
			freeze: true,
			freeze_message: __("Reissuing books"),
		});
		frappe.show_alert({ message: __("Books reissued"), indicator: "green" });
		await fetchStudent(state.student.name);
	}

	function clearCounter() {
		state.student = null;
		state.issueBooks = [];
		studentForm.set_value("student", "");
		studentForm.set_value("reference_number", "");
		bookForm.set_value("book_identifier", "");
		renderStudent();
		renderIssueBooks();
		renderReturns();
	}
};

function escapeHtml(value) {
	return String(value == null ? "" : value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}
