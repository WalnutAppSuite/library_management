import base64
import io
import json
import os
import re
import urllib.parse
import urllib.request
from contextlib import suppress

import frappe
from frappe import _
from frappe.utils import add_days, cint, cstr, getdate, today


ISBN_RE = re.compile(r"(?:(?:97[89])[\-\s]?)?(?:\d[\-\s]?){9}[\dXx]")


def _as_dict(value):
	if not value:
		return {}
	if isinstance(value, dict):
		return value
	if isinstance(value, str):
		return json.loads(value)
	return dict(value)


def _as_list(value):
	if not value:
		return []
	if isinstance(value, list):
		return value
	if isinstance(value, str):
		return json.loads(value)
	return list(value)


def _json_get(url, timeout=8):
	req = urllib.request.Request(url, headers={"User-Agent": "library-management/1.0"})
	with urllib.request.urlopen(req, timeout=timeout) as response:
		return json.loads(response.read().decode("utf-8"))


def normalize_isbn(value):
	value = cstr(value).upper().replace("-", "").replace(" ", "")
	value = re.sub(r"[^0-9X]", "", value)
	return value


def is_valid_isbn10(isbn):
	isbn = normalize_isbn(isbn)
	if len(isbn) != 10:
		return False
	total = 0
	for idx, char in enumerate(isbn):
		if char == "X" and idx == 9:
			digit = 10
		elif char.isdigit():
			digit = int(char)
		else:
			return False
		total += digit * (10 - idx)
	return total % 11 == 0


def is_valid_isbn13(isbn):
	isbn = normalize_isbn(isbn)
	if len(isbn) != 13 or not isbn.isdigit():
		return False
	total = sum((1 if idx % 2 == 0 else 3) * int(char) for idx, char in enumerate(isbn))
	return total % 10 == 0


def is_valid_isbn(isbn):
	isbn = normalize_isbn(isbn)
	return is_valid_isbn10(isbn) or is_valid_isbn13(isbn)


def extract_isbn_from_text(text):
	for match in ISBN_RE.findall(cstr(text)):
		isbn = normalize_isbn(match)
		if is_valid_isbn(isbn):
			return isbn
	return ""


def _settings_value(fieldname, default=None):
	with suppress(Exception):
		value = frappe.db.get_single_value("Library Management Settings", fieldname)
		return default if value is None else value
	return default


def _settings_password(fieldname):
	with suppress(Exception):
		return frappe.get_single("Library Management Settings").get_password(fieldname)
	return None


@frappe.whitelist()
def get_user_library_branch():
	"""Resolve the logged-in user's library branch (a School).

	Branch scoping uses a standard Frappe **User Permission** on School, so the
	app needs only Frappe + Education — no HR/HRMS dependency. As an optional
	fallback, a linked Employee's school/branch is used when HR is installed
	(keeps existing HR-based setups working). Returns ``is_ho=True`` (all
	branches) when no single branch can be determined.
	"""
	branch = _user_permitted_school()

	if not branch and frappe.db.exists("DocType", "Employee"):
		branch = _employee_branch(frappe.session.user)

	is_ho = (
		not branch
		or cstr(branch).strip().upper() == "HO"
		or not frappe.db.exists("School", branch)
	)
	return {"branch": "" if is_ho else branch, "is_ho": is_ho}


def _user_permitted_school():
	"""The single School this user is restricted to via User Permission, if exactly one."""
	schools = frappe.get_all(
		"User Permission",
		filters={"user": frappe.session.user, "allow": "School"},
		pluck="for_value",
	)
	schools = [s for s in schools if frappe.db.exists("School", s)]
	return schools[0] if len(schools) == 1 else ""


def _employee_branch(user):
	"""Optional HR fallback: a linked Employee's school/branch, when HR is present.

	``school`` is a non-core field that only some sites add, so read it only
	when the Employee doctype actually has it.
	"""
	fields = ["school"] if frappe.get_meta("Employee").has_field("school") else []
	fields.append("branch")
	row = frappe.db.get_value("Employee", {"user_id": user}, fields, as_dict=True)
	if not row:
		return ""
	cand = row.get("school") or row.get("branch")
	return cand if cand and frappe.db.exists("School", cand) else ""


@frappe.whitelist()
def get_next_accession_number(branch=None):
	filters = []
	values = {}
	if branch:
		filters.append("branch = %(branch)s")
		values["branch"] = branch
	where = " where " + " and ".join(filters) if filters else ""
	result = frappe.db.sql(
		f"""
		select max(cast(accession_number as unsigned))
		from `tabLibrary Books`
		{where}
		{"and" if where else "where"} accession_number regexp '^[0-9]+$'
		""".replace("where  and", "where"),
		values,
	)
	max_value = cint(result[0][0]) if result and result[0] else 0
	return str(max_value + 1)


def _metadata_from_google(isbn):
	data = _json_get(
		"https://www.googleapis.com/books/v1/volumes?"
		+ urllib.parse.urlencode({"q": f"isbn:{isbn}", "maxResults": 1})
	)
	items = data.get("items") or []
	if not items:
		return {}
	info = items[0].get("volumeInfo") or {}
	identifiers = {i.get("type"): i.get("identifier") for i in info.get("industryIdentifiers") or []}
	return {
		"isbn": identifiers.get("ISBN_13") or identifiers.get("ISBN_10") or isbn,
		"book_name": info.get("title") or "",
		"author": ", ".join(info.get("authors") or []),
		"publisher": info.get("publisher") or "",
		"pages": info.get("pageCount") or "",
		"language": info.get("language") or "",
		"year_of_publication": cstr(info.get("publishedDate") or "")[:4],
		"source": "google_books",
		"confidence": 85,
	}


def _metadata_from_open_library(isbn):
	data = _json_get(f"https://openlibrary.org/isbn/{urllib.parse.quote(isbn)}.json")
	authors = []
	for author in data.get("authors") or []:
		key = author.get("key")
		if not key:
			continue
		with suppress(Exception):
			authors.append(_json_get(f"https://openlibrary.org{key}.json").get("name"))
	return {
		"isbn": isbn,
		"book_name": data.get("title") or "",
		"author": ", ".join([a for a in authors if a]),
		"publisher": ", ".join(data.get("publishers") or []),
		"pages": data.get("number_of_pages") or "",
		"language": "",
		"year_of_publication": cstr(data.get("publish_date") or "")[-4:],
		"source": "open_library",
		"confidence": 75,
	}


@frappe.whitelist()
def lookup_book_metadata_by_isbn(isbn):
	isbn = normalize_isbn(isbn)
	if not is_valid_isbn(isbn):
		return {"isbn": isbn, "source": "manual", "confidence": 0}

	if not cint(_settings_value("enable_external_metadata_lookup", 1)):
		return {"isbn": isbn, "source": "manual", "confidence": 0}

	for getter in (_metadata_from_google, _metadata_from_open_library):
		with suppress(Exception):
			metadata = getter(isbn)
			if metadata and metadata.get("book_name"):
				return metadata

	return {"isbn": isbn, "source": "manual", "confidence": 0}


def _call_openai_for_book(front_image=None, back_image=None):
	if not cint(_settings_value("enable_ai_fallback", 0)):
		return {}

	api_key = _settings_password("openai_api_key") or os.environ.get("OPENAI_API_KEY")
	if not api_key:
		return {}

	model = _settings_value("ai_model", "gpt-5.4-mini")
	content = [
		{
			"type": "input_text",
			"text": (
				"Extract library book metadata from these cover images. Return only JSON with keys "
				"isbn, book_name, author, publisher, pages, language, edition, year_of_publication, "
				"price, confidence, uncertainty_notes. Use empty strings for unknown fields."
			),
		}
	]
	for image in (front_image, back_image):
		if image:
			content.append({"type": "input_image", "image_url": image})

	payload = {
		"model": model,
		"input": [{"role": "user", "content": content}],
		"text": {"format": {"type": "json_object"}},
	}
	req = urllib.request.Request(
		"https://api.openai.com/v1/responses",
		data=json.dumps(payload).encode("utf-8"),
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=30) as response:
		data = json.loads(response.read().decode("utf-8"))

	text = ""
	for item in data.get("output") or []:
		for content_item in item.get("content") or []:
			if content_item.get("type") in {"output_text", "text"}:
				text += content_item.get("text") or ""
	return json.loads(text) if text else {}


@frappe.whitelist()
def extract_book_metadata(front_image=None, back_image=None, branch=None, scanned_code=None):
	isbn = ""
	source = "manual"
	confidence = 0

	for candidate in (scanned_code, front_image, back_image):
		isbn = extract_isbn_from_text(candidate)
		if isbn:
			source = "scanned_isbn"
			confidence = 95
			break

	metadata = {}
	if isbn:
		metadata = lookup_book_metadata_by_isbn(isbn)
		source = metadata.get("source") or source
		confidence = metadata.get("confidence") or confidence

	if not metadata or not metadata.get("book_name"):
		with suppress(Exception):
			metadata = _call_openai_for_book(front_image, back_image)
			if metadata:
				source = "ai_fallback"
				confidence = metadata.get("confidence") or 55

	if not metadata:
		metadata = {}

	if isbn and not metadata.get("isbn"):
		metadata["isbn"] = isbn
	metadata.setdefault("branch", branch)
	metadata["source"] = source
	metadata["confidence"] = confidence
	if branch and not metadata.get("accession_number"):
		metadata["accession_number"] = get_next_accession_number(branch)
	return metadata


def _qr_payload(book):
	# Validate that either accession_number or isbn is present
	if not (book.accession_number or book.isbn):
		frappe.throw(_("This book does not have an accession number or ISBN number. It is required for QR generation."))
	
	return {
		"v": 1,
		"doctype": "Library Books",
		"book_id": book.name,
		"accession_number": book.accession_number,
		"isbn": book.isbn,
		"title": book.book_name,
		"author": book.author,
		"publisher": book.publisher,
		"branch": book.branch,
		"room": book.get("room"),
		"book_shelf": book.get("book_shelf"),
	}


def _qr_image_data(payload):
	import qrcode

	qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
	qr.add_data(json.dumps(payload, separators=(",", ":")))
	qr.make(fit=True)
	image = qr.make_image(fill_color="black", back_color="white")
	buffer = io.BytesIO()
	if image.mode != "RGB":
		image = image.convert("RGB")
	image.save(buffer, format="PNG")
	return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")


@frappe.whitelist()
def generate_book_qr(book_name):
	book = frappe.get_doc("Library Books", book_name)
	payload = _qr_payload(book)
	image = _qr_image_data(payload)
	frappe.db.set_value(
		"Library Books",
		book.name,
		{
			"qr_code_payload": json.dumps(payload, separators=(",", ":")),
			"qr_code_image": f'<img src="{image}" alt="{frappe.utils.escape_html(book.book_name)}" />',
		},
	)
	return {"payload": payload, "image": image}


@frappe.whitelist()
def print_book_qr(book_name):
	return print_book_qr_labels(json.dumps([book_name]))


def _qr_img_tag(book):
	generate_book_qr(book.name)
	book.reload()
	return book.qr_code_image


def _validate_accession_unique(accession_number, branch, exclude=None):
	if not accession_number:
		return
	filters = {"accession_number": accession_number, "branch": branch}
	existing = frappe.db.get_value("Library Books", filters, "name")
	if existing and existing != exclude:
		frappe.throw(_("Accession number {0} already exists for branch {1}").format(accession_number, branch))


@frappe.whitelist()
def create_library_book_from_preview(payload):
	payload = _as_dict(payload)
	branch = payload.get("branch")
	if not branch:
		frappe.throw(_("Branch is required"))
	accession_number = cstr(payload.get("accession_number") or get_next_accession_number(branch))
	_validate_accession_unique(accession_number, branch)

	isbn = normalize_isbn(payload.get("isbn"))
	doc = frappe.get_doc(
		{
			"doctype": "Library Books",
			"isbn": isbn or "NO-ISBN",
			"book_name": payload.get("book_name") or payload.get("title") or _("Untitled Book"),
			"accession_number": accession_number,
			"author": payload.get("author") or _("Unknown"),
			"status": payload.get("status") or "Active",
			"branch": branch,
			"room": payload.get("room"),
			"book_shelf": payload.get("book_shelf"),
			"pages": payload.get("pages"),
			"publisher": payload.get("publisher"),
			"language": payload.get("language"),
			"price": payload.get("price"),
			"source_of_book": payload.get("source_of_book"),
			"quantity": 1,
			"available_quantity": 1,
			"call_no": payload.get("call_no"),
			"edition": payload.get("edition"),
			"year_of_publication": payload.get("year_of_publication"),
			"remarks": payload.get("remarks"),
			"take_home": cint(payload.get("take_home", _settings_value("default_take_home", 1))),
			"extraction_source": payload.get("source") or payload.get("extraction_source"),
			"extraction_confidence": payload.get("confidence") or payload.get("extraction_confidence"),
		}
	)
	doc.insert()
	generate_book_qr(doc.name)
	doc.reload()
	return doc.as_dict()


def _book_fields():
	return [
		"name",
		"isbn",
		"book_name",
		"accession_number",
		"author",
		"publisher",
		"pages",
		"price",
		"branch",
		"room",
		"book_shelf",
		"status",
		"take_home",
		"quantity",
		"available_quantity",
		"qr_code_payload",
	]


def _active_issue_row(book_name):
	return frappe.db.get_value(
		"Library Transaction Book",
		{
			"library_book": book_name,
			"book_status": "READING",
			"parenttype": "Library Transactions",
		},
		["name", "parent"],
		as_dict=True,
	)


def _book_match_row(book, selected_branch=None):
	book = frappe._dict(book)
	active_issue = _active_issue_row(book.name)
	wrong_branch = bool(selected_branch and book.branch and book.branch != selected_branch)
	branch_missing = bool(selected_branch and not book.branch)
	is_available = cint(book.available_quantity) > 0
	stale_unavailable = bool(not is_available and not active_issue)

	if stale_unavailable:
		frappe.db.set_value("Library Books", book.name, "available_quantity", 1, update_modified=False)
		book.available_quantity = 1
		is_available = True

	book["is_active_issue"] = bool(active_issue)
	book["branch_missing"] = branch_missing
	book["wrong_branch"] = wrong_branch
	book["can_issue"] = bool(is_available and not active_issue and not wrong_branch)
	if active_issue:
		book["availability_label"] = _("Already Issued")
		book["issue_reason"] = _("Already issued in transaction {0}").format(active_issue.parent)
	elif wrong_branch:
		book["availability_label"] = _("Wrong Branch")
		book["issue_reason"] = _("Book belongs to branch {0}").format(book.branch)
	elif branch_missing:
		book["availability_label"] = _("Available · Branch Missing")
		book["issue_reason"] = _("Legacy book without branch; allowed for exact accession search")
	elif is_available:
		book["availability_label"] = _("Available")
		book["issue_reason"] = ""
	else:
		book["availability_label"] = _("Unavailable")
		book["issue_reason"] = _("No available quantity")
	return book


@frappe.whitelist()
def get_books_for_location(branch, room=None, book_shelf=None):
	if not branch:
		frappe.throw(_("Branch is required"))

	filters = {"branch": branch}
	if room:
		filters["room"] = room
	if book_shelf:
		filters["book_shelf"] = book_shelf

	return frappe.get_all(
		"Library Books",
		filters=filters,
		fields=_book_fields(),
		order_by="cast(accession_number as unsigned) asc, accession_number asc",
		limit_page_length=500,
	)


def _normalize_book_row(row, branch, room=None, book_shelf=None):
	row = _as_dict(row)
	return {
		"isbn": normalize_isbn(row.get("isbn")) or "NO-ISBN",
		"book_name": cstr(row.get("book_name") or row.get("title")).strip() or _("Untitled Book"),
		"accession_number": cstr(row.get("accession_number")).strip(),
		"author": cstr(row.get("author")).strip() or _("Unknown"),
		"publisher": cstr(row.get("publisher")).strip(),
		"pages": cstr(row.get("pages")).strip(),
		"price": cstr(row.get("price")).strip(),
		"branch": branch,
		"room": room,
		"book_shelf": cstr(book_shelf).strip(),
		"status": row.get("status") or "Active",
		"take_home": cint(row.get("take_home", _settings_value("default_take_home", 1))),
		"quantity": 1,
		"available_quantity": 1 if row.get("available_quantity") in (None, "") else cint(row.get("available_quantity")),
	}


@frappe.whitelist()
def save_library_books(rows, branch, room=None, book_shelf=None):
	rows = _as_list(rows)
	if not branch:
		frappe.throw(_("Branch is required"))
	if not rows:
		frappe.throw(_("Add at least one book"))

	# Title, Author, Publisher and Accession Number are mandatory for every book.
	required = [("book_name", _("Title")), ("author", _("Author")), ("publisher", _("Publisher")), ("accession_number", _("Accession Number"))]
	problems = []
	for raw in rows:
		raw = _as_dict(raw)
		if not (raw.get("isbn") or raw.get("book_name") or raw.get("author") or raw.get("publisher") or raw.get("name")):
			continue
		missing = [label for field, label in required if not cstr(raw.get(field)).strip()]
		if missing:
			problems.append("{0}: {1}".format(raw.get("book_name") or raw.get("isbn") or _("Unnamed Book"), ", ".join(missing)))
	if problems:
		frappe.throw(_("Title, Author, Publisher and Accession Number are required for every book.") + "<br>" + "<br>".join(problems))

	saved = []
	next_accession = cint(get_next_accession_number(branch))
	for raw in rows:
		raw = _as_dict(raw)
		if not (raw.get("isbn") or raw.get("book_name") or raw.get("author") or raw.get("publisher") or raw.get("name")):
			continue
		values = _normalize_book_row(raw, branch, room, book_shelf)
		if not values["accession_number"]:
			values["accession_number"] = str(next_accession)
			next_accession += 1
		_validate_accession_unique(values["accession_number"], branch, exclude=raw.get("name"))

		if raw.get("name") and frappe.db.exists("Library Books", raw.get("name")):
			doc = frappe.get_doc("Library Books", raw.get("name"))
			was_reading = cint(doc.available_quantity) <= 0
			for fieldname, value in values.items():
				if fieldname == "available_quantity" and was_reading:
					continue
				doc.set(fieldname, value)
			doc.save()
		else:
			doc = frappe.get_doc({"doctype": "Library Books", **values})
			doc.insert()

		generate_book_qr(doc.name)
		doc.reload()
		saved.append(frappe.db.get_value("Library Books", doc.name, _book_fields(), as_dict=True))

	frappe.db.commit()
	return saved


@frappe.whitelist()
def print_book_qr_labels(book_names):
	book_names = _as_list(book_names)
	if not book_names:
		frappe.throw(_("Select at least one book"))

	book_names = [name for name in _as_list(book_names)]

	# Generate QR codes and book info only for books with accession numbers.
	books_with_qr = []
	for name in book_names:
		book = frappe.get_doc("Library Books", name)
		if not book.accession_number:
			continue
		books_with_qr.append({
			"qr": _qr_img_tag(book),
			"accession": frappe.utils.escape_html(book.accession_number),
			"title": frappe.utils.escape_html(book.book_name[:30]) if book.book_name else "",
		})

	# Generate grid layout: Each row contains 2 books with 3 QR codes each (6 QR codes per row)
	html_rows = []
	for i in range(0, len(books_with_qr), 2):
		left = books_with_qr[i]
		right = books_with_qr[i + 1] if i + 1 < len(books_with_qr) else None
		row_html = '<div class="book-row">'
		for book_item in (left, right):
			if not book_item:
				continue
			row_html += f'''
			<div class="book-block">
				<div class="qr-container">
					<div class="qr-item">
						{book_item["qr"]}
						<div class="qr-accession">{book_item["accession"]}</div>
					</div>
					<div class="qr-item">
						{book_item["qr"]}
						<div class="qr-accession">{book_item["accession"]}</div>
					</div>
					<div class="qr-item">
						{book_item["qr"]}
						<div class="qr-accession">{book_item["accession"]}</div>
					</div>
				</div>
				<div class="book-info">
					<div class="book-title">{book_item["title"]}</div>
				</div>
			</div>
			'''
		row_html += '</div>'
		html_rows.append(row_html)

	html = f"""<!doctype html>
	<html>
	<head>
		<meta charset="UTF-8">
		<title>Library QR Labels - Print Preview</title>
		<style>
			@page {{
				size: A4;
				margin: 5mm;
			}}
			* {{
				margin: 0;
				padding: 0;
				box-sizing: border-box;
			}}
			html, body {{
				width: 100%;
				height: 100%;
			}}
			body {{
				font-family: Arial, sans-serif;
				color: #111827;
				background: #f5f5f5;
				padding: 20px;
			}}
			.print-container {{
				background: white;
				max-width: 210mm;
				height: auto;
				margin: 0 auto;
				padding: 3mm;
				box-shadow: none;
				display: flex;
				flex-direction: column;
			}}
			.print-header {{
				text-align: center;
				margin-bottom: 5mm;
				padding-bottom: 3mm;
			}}
			.print-header h2 {{
				font-size: 14px;
				margin: 0;
			}}
			.print-content {{
				flex: 1;
				overflow-y: auto;
			}}
			.print-actions {{
				text-align: center;
				margin-top: 6mm;
				padding-top: 6mm;
			}}
			.print-actions button {{
				padding: 6px 14px;
				margin: 0 4px;
				font-size: 13px;
				cursor: pointer;
				border: none;
				border-radius: 4px;
				background: #0066cc;
				color: white;
			}}
			.print-actions button.cancel {{
				background: #6c757d;
			}}
			.print-actions button.cancel:hover {{
				background: #5a6268;
			}}
			.book-row {{
				display: flex;
				flex-direction: row;
				justify-content: space-between;
				align-items: flex-start;
				border: none;
				padding: 0;
				gap: 4mm;
				margin-bottom: 2mm;
				page-break-inside: avoid;
				width: 100%;
			}}
			.book-block {{
				display: flex;
				flex-direction: column;
				align-items: center;
				justify-content: flex-start;
				flex: 1;
				border: none;
				padding: 0;
				gap: 1mm;
			}}
			.qr-container {{
				display: flex;
				gap: 1.5mm;
				justify-content: center;
				align-items: center;
				width: 100%;
				flex-wrap: nowrap;
			}}
			.qr-item {{
				display: flex;
				flex-direction: column;
				align-items: center;
				justify-content: flex-start;
				width: 22mm;
				height: auto;
				border: none;
				flex-shrink: 0;
			}}
			.qr-item img {{
				width: 22mm;
				height: 22mm;
				object-fit: contain;
				image-rendering: crisp-edges;
				-webkit-print-color-adjust: exact;
				print-color-adjust: exact;
			}}
			.book-info {{
				display: flex;
				flex-direction: column;
				align-items: center;
				gap: 0.5mm;
				width: 100%;
			}}
			.book-title {{
				font-size: 6px;
				color: #666;
				text-align: center;
				word-break: break-word;
				max-width: 70mm;
				max-height: 6mm;
				overflow: hidden;
				line-height: 1.1;
			}}
			.qr-accession {{
				font-size: 7px;
				font-weight: 700;
				text-align: center;
				margin-top: 1mm;
				word-break: break-all;
				max-width: 18mm;
				line-height: 1.1;
			}}
			@media print {{
				body {{
					background: white;
					padding: 0;
					margin: 0;
				}}
				.print-container {{
					max-width: none;
					height: auto;
					box-shadow: none;
					margin: 0;
					padding: 5mm;
				}}
				.print-header {{
					display: none;
				}}
				.print-actions {{
					display: none;
				}}
				.book-row {{
					margin-bottom: 2mm;
				}}
			}}
		</style>
	</head>
	<body>
		<div class="print-container">
			<div class="print-header">
				<h2>Library QR Labels - Print Preview</h2>
				<p style="font-size: 12px; color: #666; margin-top: 5px;">Total Books: {len(books_with_qr)}</p>
			</div>
			<div class="print-content">
				{"".join(html_rows)}
			</div>
			<div class="print-actions">
				<button onclick="window.print()">Print</button>
				<button class="cancel" onclick="window.close()">Close</button>
			</div>
		</div>
	</body>
	</html>"""
	return html


@frappe.whitelist()
def resolve_book_matches(identifier, branch=None, room=None, book_shelf=None):
	identifier = _parse_qr_identifier(identifier)
	normalized = normalize_isbn(identifier)
	books = []
	is_exact_lookup = bool(frappe.db.exists("Library Books", identifier) or identifier != normalized)

	if frappe.db.exists("Library Books", identifier):
		books = frappe.get_all("Library Books", filters={"name": identifier}, fields=_book_fields(), limit_page_length=1)
	elif identifier:
		accession_filters = {"accession_number": identifier}
		if branch:
			accession_filters["branch"] = branch
		books = frappe.get_all(
			"Library Books",
			filters=accession_filters,
			fields=_book_fields(),
			order_by="available_quantity desc, modified desc",
			limit_page_length=20,
		)

	if not books and normalized:
		isbn_filters = {"isbn": normalized}
		if room:
			isbn_filters["room"] = room
		if book_shelf:
			isbn_filters["book_shelf"] = book_shelf
		if branch:
			isbn_filters["branch"] = branch
		books = frappe.get_all(
			"Library Books",
			filters=isbn_filters,
			fields=_book_fields(),
			order_by="available_quantity desc, cast(accession_number as unsigned) asc, accession_number asc",
			limit_page_length=50,
		)

	books = [_book_match_row(book, branch) for book in books]
	if is_exact_lookup and branch:
		for book in books:
			if book.branch_missing:
				book.can_issue = bool(not book.is_active_issue and cint(book.available_quantity) > 0)
	if not books:
		frappe.throw(_("No available matching book found"))
	return books


def _parse_qr_identifier(identifier):
	identifier = cstr(identifier).strip()
	with suppress(Exception):
		payload = json.loads(identifier)
		if payload.get("doctype") == "Library Books":
			return payload.get("book_id") or payload.get("id") or payload.get("accession_number") or payload.get("isbn")
		if payload.get("id") or payload.get("accession_number") or payload.get("isbn"):
			return payload.get("id") or payload.get("accession_number") or payload.get("isbn")
	return identifier


@frappe.whitelist()
def resolve_student(identifier, branch=None):
	identifier = cstr(identifier).strip()
	with suppress(Exception):
		parts = identifier.split("/")
		if len(parts) >= 3:
			branch = branch or parts[-2]
			identifier = parts[-1]

	if frappe.db.exists("Student", identifier):
		filters = {"name": identifier}
	else:
		filters = {"reference_number": identifier}
	if branch:
		filters["school"] = branch
	student = frappe.db.get_value(
		"Student",
		filters,
		["name", "student_name", "first_name", "middle_name", "last_name", "reference_number", "program", "school", "image", "user"],
		as_dict=True,
	)
	if not student:
		frappe.throw(_("No student found for reference number {0}").format(identifier))

	student["display_name"] = student.student_name or " ".join(
		[p for p in [student.first_name, student.middle_name, student.last_name] if p]
	)
	student["active_books"] = frappe.db.sql(
		"""
		SELECT ltb.name, lt.name AS parent, ltb.library_book,
		       ltb.accession_number, ltb.book_name, ltb.author, ltb.due_date
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		WHERE lt.student = %(student)s
		  AND ltb.book_status = 'READING'
		  AND ltb.parenttype = 'Library Transactions'
		ORDER BY ltb.due_date ASC
		""",
		{"student": student.name},
		as_dict=True,
	)
	student["issued_count"] = len(student["active_books"])
	student["overdue_count"] = len([row for row in student["active_books"] if row.due_date and getdate(row.due_date) < getdate(today())])

	# Full issue/return history for the Library Counter, reusing the same
	# join used to populate the Student form's custom_library_books table.
	from library_management.library_management.doctype.library_books_student_table.library_books_student_table import (
		rows_for_student,
	)

	student["history"] = rows_for_student(student.name)
	return student


@frappe.whitelist()
def resolve_book(identifier, branch=None, require_available=False):
	identifier = _parse_qr_identifier(identifier)
	filters = {}
	if frappe.db.exists("Library Books", identifier):
		filters["name"] = identifier
	else:
		filters = {"accession_number": identifier}
		if not frappe.db.exists("Library Books", filters):
			filters = {"isbn": normalize_isbn(identifier)}
	if branch:
		filters["branch"] = branch

	books = frappe.get_all(
		"Library Books",
		filters=filters,
		fields=[
			"name",
			"isbn",
			"book_name",
			"accession_number",
			"author",
			"publisher",
			"branch",
			"room",
			"book_shelf",
			"status",
			"take_home",
			"quantity",
			"available_quantity",
		],
		order_by="available_quantity desc, accession_number asc",
		limit_page_length=20,
	)
	if require_available:
		books = [book for book in books if cint(book.available_quantity) > 0]
	if not books:
		frappe.throw(_("No matching book found"))
	return books[0] if len(books) == 1 else {"matches": books}


def _loan_period():
	return cint(_settings_value("loan_period", 7)) or 7


def _book_child_from_doc(book, issue_date=None, due_date=None, status="READING"):
	issue_date = issue_date or today()
	due_date = due_date or add_days(issue_date, _loan_period())
	return {
		"library_book": book.name,
		"isbn": book.isbn,
		"accession_number": book.accession_number,
		"book_name": book.book_name,
		"author": book.author,
		"publisher": book.publisher,
		"issue_date": issue_date,
		"due_date": due_date,
		"book_status": status,
	}


def _assert_can_issue(book, branch=None):
	if book.status != "Active":
		frappe.throw(_("{0} is not active").format(book.book_name))
	if not cint(book.take_home):
		frappe.throw(_("{0} is not allowed for home reading").format(book.book_name))
	if branch and book.branch != branch and _settings_value("branch_override_role", "System Manager") not in frappe.get_roles():
		frappe.throw(_("{0} belongs to branch {1}").format(book.book_name, book.branch))
	if cint(book.available_quantity) <= 0:
		frappe.throw(_("{0} is not available").format(book.book_name))


def _update_student_book_count(student_name):
	count = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		WHERE lt.student = %s
		  AND ltb.book_status = 'READING'
		  AND ltb.parenttype = 'Library Transactions'
		""",
		student_name,
	)[0][0]
	frappe.db.set_value("Student", student_name, "custom_number_of_books_issued", str(count))


@frappe.whitelist()
def create_issue_transaction(student, books, branch=None):
	books = _as_list(books)
	if not student:
		frappe.throw(_("Student is required"))
	if not books:
		frappe.throw(_("Add at least one book"))

	seen = set()
	tx = frappe.new_doc("Library Transactions")
	tx.student = student
	student_info = frappe.db.get_value("Student", student, ["user", "program", "school"], as_dict=True)
	if student_info:
		tx.student_email = student_info.user
		tx.classs = student_info.program
		tx.branch = branch or student_info.school
	branch = branch or tx.branch

	for raw in books:
		identifier = raw.get("library_book") or raw.get("name") or raw.get("accession_number") or raw.get("isbn")
		book_name = resolve_book(identifier, branch=branch, require_available=True)
		if isinstance(book_name, dict) and book_name.get("matches"):
			book_name = book_name["matches"][0]
		book = frappe.get_doc("Library Books", book_name.name)
		if book.name in seen:
			frappe.throw(_("Book {0} is already added").format(book.book_name))
		seen.add(book.name)
		_assert_can_issue(book, branch)
		tx.append("books", _book_child_from_doc(book, raw.get("issue_date"), raw.get("due_date")))

	tx.insert()
	frappe.db.commit()
	return tx.as_dict()


def _active_issue_rows(student=None):
	"""READING transaction-book rows, optionally scoped to one student.

	Scoping by student in SQL keeps the result bounded (the old global scan
	capped at 500 rows could silently miss a student's books)."""
	conditions = ["ltb.book_status = 'READING'", "ltb.parenttype = 'Library Transactions'"]
	values = {}
	if student:
		conditions.append("lt.student = %(student)s")
		values["student"] = student
	where = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT ltb.name, ltb.parent, lt.student, ltb.library_book,
		       ltb.isbn, ltb.accession_number, ltb.reissue_count
		FROM `tabLibrary Transaction Book` ltb
		JOIN `tabLibrary Transactions` lt ON lt.name = ltb.parent
		WHERE {where}
		""",
		values,
		as_dict=True,
	)


def _selected_targets(books):
	"""Split selected book payloads into transaction-book row ids and free-text
	identifiers. Matching on the row id (txn_book) lets the counter act on rows
	that have no linked Library Books record (legacy rows with NULL library_book)."""
	row_names = {item.get("txn_book") for item in books if item.get("txn_book")}
	identifiers = {
		_parse_qr_identifier(item.get("library_book") or item.get("name") or item.get("accession_number") or item.get("isbn"))
		for item in books
	}
	identifiers.discard("")
	identifiers.discard(None)
	return row_names, identifiers


def _row_is_selected(row, row_names, identifiers):
	return row.name in row_names or bool({row.library_book, row.isbn, row.accession_number} & identifiers)


@frappe.whitelist()
def return_books(student=None, books=None, branch=None):
	books = _as_list(books)
	if not books:
		frappe.throw(_("Select at least one book to return"))

	row_names, identifiers = _selected_targets(books)
	updated_transactions = set()

	for row in _active_issue_rows(student):
		if not _row_is_selected(row, row_names, identifiers):
			continue
		frappe.db.set_value("Library Transaction Book", row.name, {"book_status": "RETURNED", "return_date": today()})
		if row.library_book:
			frappe.db.set_value("Library Books", row.library_book, "available_quantity", 1)
		updated_transactions.add(row.parent)

	if not updated_transactions:
		frappe.throw(_("No active issued books matched"))

	updated_students = {
		frappe.db.get_value("Library Transactions", txn, "student") for txn in updated_transactions
	}
	for student_name in updated_students:
		_update_student_book_count(student_name)
	frappe.db.commit()
	return {"returned": len(updated_transactions), "transactions": list(updated_transactions)}


@frappe.whitelist()
def reissue_books(student=None, books=None, branch=None):
	"""Renew the given issued books: extend due_date to today + loan_period.

	Mirrors return_books (same active-row scan + matching) but keeps each book
	in READING status, bumps reissue_count, and leaves availability untouched.
	"""
	books = _as_list(books)
	if not books:
		frappe.throw(_("Select at least one book to reissue"))

	row_names, identifiers = _selected_targets(books)
	new_due_date = add_days(today(), _loan_period())
	updated_rows = 0

	for row in _active_issue_rows(student):
		if not _row_is_selected(row, row_names, identifiers):
			continue
		frappe.db.set_value(
			"Library Transaction Book",
			row.name,
			{"due_date": new_due_date, "reissue_count": cint(row.reissue_count) + 1},
		)
		updated_rows += 1

	if not updated_rows:
		frappe.throw(_("No active issued books matched"))

	frappe.db.commit()
	return {"reissued": updated_rows, "due_date": str(new_due_date)}


@frappe.whitelist()
def update_all_due_days():
	students = frappe.db.sql(
		"""
		SELECT DISTINCT lt.student
		FROM `tabLibrary Transactions` lt
		JOIN `tabLibrary Transaction Book` ltb ON ltb.parent = lt.name
		WHERE ltb.book_status = 'READING' AND ltb.parenttype = 'Library Transactions'
		""",
		as_dict=True,
	)
	for row in students:
		_update_student_book_count(row.student)


def populate_student_library_books_table(doc, method=None):
	"""onload hook for Student — populate the virtual `custom_library_books`
	child table by joining Library Transaction Book ↔ Library Transactions
	filtered by student. Frappe v15 doesn't auto-fetch virtual child tables
	on parent load, so the field arrives empty unless we fill it here."""
	if not getattr(doc, "name", None) or doc.is_new():
		return
	if not doc.meta.get_field("custom_library_books"):
		return
	if not _has_doctype("Library Books Student Table") or not _has_doctype("Library Transaction Book"):
		return
	from library_management.library_management.doctype.library_books_student_table.library_books_student_table import rows_for_student
	rows = rows_for_student(doc.name) or []
	doc.set("custom_library_books", rows)


def _has_doctype(name):
	try:
		return bool(frappe.db.exists("DocType", name))
	except Exception:
		return False
