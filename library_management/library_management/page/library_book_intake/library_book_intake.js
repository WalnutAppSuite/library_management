frappe.pages["library-book-intake"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Library Book Intake"),
		single_column: true,
	});

	const state = {
		branch: "",
		room: "",
		book_shelf: "",
		rows: [],
		selected: new Set(),
	};

	page.main.html(`
		<div class="library-intake">
			<div class="intake-topbar">
				<div>
					<h2>${__("Shelf Book Entry")}</h2>
					<div class="subtitle">${__("Select a location, maintain books in a table, and print three QR labels per book.")}</div>
				</div>
				<div class="summary-pill" id="intake-summary">${__("Select filters")}</div>
			</div>
			<div class="filter-panel">
				<div id="intake-filters"></div>
				<div class="actions">
					<button class="btn btn-default" id="load-books">${__("Load Books")}</button>
					<button class="btn btn-primary" id="add-row">${__("Add Row")}</button>
					<button class="btn btn-success" id="save-books">${__("Save")}</button>
					<button class="btn btn-default" id="print-labels">${__("Print Selected QR")}</button>
				</div>
			</div>
			<div class="table-panel">
				<div class="table-responsive">
					<table class="table intake-table">
						<thead>
							<tr>
								<th class="select-col"><input type="checkbox" id="select-all-books"></th>
								<th>${__("ISBN")}</th>
								<th>${__("Title")}</th>
								<th>${__("Author")}</th>
								<th>${__("Publisher")}</th>
								<th>${__("Pages")}</th>
								<th>${__("Price")}</th>
								<th>${__("Accession No.")}</th>
								<th>${__("QR")}</th>
								<th></th>
							</tr>
						</thead>
						<tbody id="book-rows"></tbody>
					</table>
				</div>
				<div class="empty-state" id="empty-state">${__("Choose Branch, Room, and Shelf, then load or add books.")}</div>
			</div>
		</div>
	`);

	const filterGroup = new frappe.ui.FieldGroup({
		parent: page.main.find("#intake-filters"),
		fields: [
			{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "School", reqd: 1, onchange: updateLocation },
			{ fieldname: "room", label: __("Room"), fieldtype: "Link", options: "Room", onchange: updateLocation },
			{ fieldname: "book_shelf", label: __("Book Shelf"), fieldtype: "Data", onchange: updateLocation },
		],
	});
	filterGroup.make();

	bootstrap();

	page.main.find("#load-books").on("click", loadBooks);
	page.main.find("#add-row").on("click", addRow);
	page.main.find("#save-books").on("click", saveBooks);
	page.main.find("#print-labels").on("click", printLabels);
	page.main.find("#select-all-books").on("change", function () {
		state.selected = new Set(this.checked ? state.rows.filter((row) => row.name).map((row) => row.name) : []);
		renderRows();
	});

	page.main.on("input", ".book-input", function () {
		const index = Number(this.dataset.index);
		const field = this.dataset.field;
		state.rows[index][field] = this.value;
	});

	page.main.on("change", ".row-select", function () {
		const name = this.dataset.name;
		if (!name) return;
		if (this.checked) state.selected.add(name);
		else state.selected.delete(name);
	});

	page.main.on("blur", ".isbn-input", async function () {
		const index = Number(this.dataset.index);
		const row = state.rows[index];
		if (!row || !row.isbn) return;
		await fillMetadata(index);
	});

	page.main.on("click", ".remove-row", function () {
		state.rows.splice(Number(this.dataset.index), 1);
		renderRows();
	});

	async function bootstrap() {
		const r = await frappe.call("library_management.services.get_user_library_branch");
		if (r.message && r.message.branch) {
			filterGroup.set_value("branch", r.message.branch);
			updateLocation();
		}
	}

	function updateLocation() {
		state.branch = filterGroup.get_value("branch") || "";
		state.room = filterGroup.get_value("room") || "";
		state.book_shelf = filterGroup.get_value("book_shelf") || "";
		page.main.find("#intake-summary").text(
			state.branch ? [state.branch, state.room, state.book_shelf].filter(Boolean).join(" / ") : __("Select filters")
		);
	}

	function requireLocation() {
		updateLocation();
		if (!state.branch || !state.room || !state.book_shelf) {
			frappe.msgprint(__("Select Branch, Room, and Book Shelf first."));
			return false;
		}
		return true;
	}

	async function loadBooks() {
		if (!requireLocation()) return;
		const r = await frappe.call({
			method: "library_management.services.get_books_for_location",
			args: { branch: state.branch, room: state.room, book_shelf: state.book_shelf },
			freeze: true,
			freeze_message: __("Loading books"),
		});
		state.rows = (r.message || []).map(normalizeRow);
		state.selected = new Set();
		renderRows();
	}

	async function addRow() {
		if (!requireLocation()) return;
		let accession = String(nextLocalAccession() || "");
		try {
			if (!accession) {
				const r = await frappe.call("library_management.services.get_next_accession_number", { branch: state.branch });
				accession = r.message || "";
			}
		} catch (e) {
			accession = "";
		}
		state.rows.push(
			normalizeRow({
				is_new: true,
				branch: state.branch,
				room: state.room,
				book_shelf: state.book_shelf,
				accession_number: accession,
				status: "Active",
				quantity: 1,
				available_quantity: 1,
			})
		);
		renderRows();
	}

	function nextLocalAccession() {
		const numeric = state.rows
			.map((row) => String(row.accession_number || ""))
			.filter((value) => /^[0-9]+$/.test(value))
			.map((value) => Number(value));
		if (!numeric.length) return "";
		return Math.max(...numeric) + 1;
	}

	async function fillMetadata(index) {
		const row = state.rows[index];
		if (!row || row._lookup_done === row.isbn) return;
		row._lookup_done = row.isbn;
		try {
			const r = await frappe.call("library_management.services.lookup_book_metadata_by_isbn", { isbn: row.isbn });
			const meta = r.message || {};
			row.book_name = row.book_name || meta.book_name || "";
			row.author = row.author || meta.author || "";
			row.publisher = row.publisher || meta.publisher || "";
			row.pages = row.pages || meta.pages || "";
			renderRows();
		} catch (e) {
			frappe.show_alert({ message: __("ISBN lookup skipped"), indicator: "orange" });
		}
	}

	async function saveBooks() {
		if (!requireLocation()) return;
		const rows = state.rows.filter((row) => row.name || row.isbn || row.book_name || row.author || row.publisher);
		if (!rows.length) {
			frappe.msgprint(__("Add at least one book."));
			return;
		}
		const r = await frappe.call({
			method: "library_management.services.save_library_books",
			args: { rows, branch: state.branch, room: state.room, book_shelf: state.book_shelf },
			freeze: true,
			freeze_message: __("Saving books"),
		});
		state.rows = (r.message || []).map(normalizeRow);
		state.selected = new Set(state.rows.map((row) => row.name).filter(Boolean));
		renderRows();
		frappe.show_alert({ message: __("Books saved"), indicator: "green" });
	}

	function printLabels() {
		const bookNames = Array.from(state.selected);
		if (!bookNames.length) {
			frappe.msgprint(__("Select saved books to print QR labels."));
			return;
		}
		const payload = encodeURIComponent(JSON.stringify(bookNames));
		window.open(`/api/method/library_management.services.print_book_qr_labels?book_names=${payload}`, "_blank");
	}

	function renderRows() {
		const tbody = page.main.find("#book-rows");
		tbody.html(
			state.rows
				.map(
					(row, index) => `
					<tr>
						<td class="select-col">
							<input type="checkbox" class="row-select" data-name="${escapeHtml(row.name || "")}" ${row.name && state.selected.has(row.name) ? "checked" : ""} ${row.name ? "" : "disabled"}>
						</td>
						<td><input class="form-control book-input isbn-input" data-index="${index}" data-field="isbn" value="${escapeHtml(row.isbn)}"></td>
						<td><input class="form-control book-input" data-index="${index}" data-field="book_name" value="${escapeHtml(row.book_name)}"></td>
						<td><input class="form-control book-input" data-index="${index}" data-field="author" value="${escapeHtml(row.author)}"></td>
						<td><input class="form-control book-input" data-index="${index}" data-field="publisher" value="${escapeHtml(row.publisher)}"></td>
						<td><input class="form-control book-input compact" data-index="${index}" data-field="pages" value="${escapeHtml(row.pages)}"></td>
						<td><input class="form-control book-input compact" data-index="${index}" data-field="price" value="${escapeHtml(row.price)}"></td>
						<td><input class="form-control book-input compact" data-index="${index}" data-field="accession_number" value="${escapeHtml(row.accession_number)}"></td>
						<td class="qr-cell">
							<span class="${row.qr_code_payload ? "qr-ready" : "qr-pending"}">${row.qr_code_payload ? __("Ready") : __("After Save")}</span>
						</td>
						<td><button class="btn btn-xs btn-default remove-row" data-index="${index}">${__("Remove")}</button></td>
					</tr>
				`
				)
				.join("")
		);
		page.main.find("#empty-state").toggle(!state.rows.length);
		page.main.find("#select-all-books").prop("checked", !!state.rows.length && state.rows.filter((row) => row.name).every((row) => state.selected.has(row.name)));
	}
};

function normalizeRow(row) {
	row = row || {};
	return {
		name: row.name || "",
		isbn: row.isbn || "",
		book_name: row.book_name || "",
		author: row.author || "",
		publisher: row.publisher || "",
		pages: row.pages || "",
		price: row.price || "",
		accession_number: row.accession_number || "",
		branch: row.branch || "",
		room: row.room || "",
		book_shelf: row.book_shelf || "",
		status: row.status || "Active",
		take_home: row.take_home == null ? 1 : row.take_home,
		quantity: row.quantity || 1,
		available_quantity: row.available_quantity == null ? 1 : row.available_quantity,
		qr_code_payload: row.qr_code_payload || "",
	};
}

function escapeHtml(value) {
	return String(value == null ? "" : value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}
