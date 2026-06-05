# Technical Reference

Developer-facing documentation for the **Library Management** Frappe app: architecture, data model,
backend API, controller logic, integrations, install/migration, and dev setup.

- [Architecture overview](#architecture-overview)
- [Data model](#data-model)
- [Backend API](#backend-api)
- [Controller logic](#controller-logic)
- [Integrations & hooks](#integrations--hooks)
- [Install & migration](#install--migration)
- [External services](#external-services)
- [Developer setup](#developer-setup)

Related: [flows.md](flows.md) (diagrams) · [reports.md](reports.md) · [user-guide.md](user-guide.md)

---

## Architecture overview

A standard [Frappe](https://frappeframework.com/) v15 app. The module name is **Library
Management**. Key directories (under `library_management/library_management/`):

```
doctype/      # 5 doctypes (data model + controllers)
page/         # 2 custom desk pages (Library Counter, Add Library Books)
report/       # 5 Script Reports (circulation + inventory)
../services.py    # all whitelisted API + business logic
../hooks.py       # app hooks (events, scheduler, install/migrate)
../migrate.py     # after_migrate: maintain Student custom field
../setup/install.py  # after_install: run healing patches on fresh install
../patches/       # data/schema migration patches
```

Requirements: Frappe `>=15.0.0,<16.0.0`, Python `>=3.10`, and the `qrcode` Python package (declared
in [`pyproject.toml`](../pyproject.toml)).

The two desk pages are thin clients: their JS calls whitelisted methods in `services.py`. Almost
all business logic lives server-side.

---

## Data model

Five doctypes. Field tables below list the meaningful fields (framework/system fields omitted).

### Library Books

The book master. One record per title/copy-group. Naming: `B.######` (expression).

| Field                                                                      | Type          | Notes                                                |
| -------------------------------------------------------------------------- | ------------- | ---------------------------------------------------- |
| `isbn`                                                                     | Data          | **Required**                                         |
| `book_name`                                                                | Data          | **Required**, title field                            |
| `accession_number`                                                         | Data          | Unique per branch (enforced in controller)           |
| `author`                                                                   | Data          | **Required**                                         |
| `status`                                                                   | Select        | `Active` / `Inactive` / `Discontinued`, **required** |
| `branch`                                                                   | Link → School | **Required**                                         |
| `room`                                                                     | Link → Room   |                                                      |
| `book_shelf`                                                               | Data          |                                                      |
| `quantity`                                                                 | Int           | **Required**, total copies                           |
| `available_quantity`                                                       | Int           | **Required**, copies currently available             |
| `take_home`                                                                | Check         | **Required**, may be borrowed if 1                   |
| `pages`, `publisher`, `language`, `price`, `source_of_book`, `image`       | Data/Attach   | Catalogue metadata                                   |
| `bill_no_and_date`, `call_no`, `edition`, `year_of_publication`, `remarks` | Data          | Catalogue metadata                                   |
| `qr_code_payload`                                                          | Long Text     | read-only, JSON payload                              |
| `qr_code_image`                                                            | Code(HTML)    | read-only, embedded `<img>` data-URI                 |
| `extraction_source`, `extraction_confidence`                               | Data/Percent  | read-only, set by AI/ISBN extraction                 |

Controller [`library_books.py`](../library_management/library_management/doctype/library_books/library_books.py):
`validate()` normalizes `quantity` (falsy → 1), defaults `available_quantity` to `quantity`, and
enforces accession-number uniqueness within a branch.

### Library Transactions

A per-student borrowing record holding a multi-book child table.

| Field                       | Type                             | Notes                                                     |
| --------------------------- | -------------------------------- | --------------------------------------------------------- |
| `student`                   | Link → Student                   | **Required**                                              |
| `classs`                    | Data                             | fetched from `student.program`                            |
| `branch`                    | Data                             | fetched from `student.school`                             |
| `student_email`             | Data                             | fetched from `student.user`                               |
| `books`                     | Table → Library Transaction Book | the issued copies                                         |
| _legacy single-book fields_ | (hidden)                         | kept for backward compatibility / normalized into `books` |

### Library Transaction Book (child)

One row per issued copy inside a transaction.

| Field                                                          | Type                 | Notes                                          |
| -------------------------------------------------------------- | -------------------- | ---------------------------------------------- |
| `library_book`                                                 | Link → Library Books | the copy (may be NULL on legacy migrated rows) |
| `isbn`, `accession_number`, `book_name`, `author`, `publisher` | Data                 | denormalized from the book                     |
| `issue_date`                                                   | Date                 |                                                |
| `due_date`                                                     | Date                 |                                                |
| `return_date`                                                  | Date                 |                                                |
| `book_status`                                                  | Select               | `READING` / `RETURNED`                         |
| `reissue_count`                                                | Int                  | number of times renewed (default 0)            |

### Library Books Student Table (child, virtual-style)

Rendered on the **Student** form as the `custom_library_books` table. Not stored as authoritative
data — populated live (see [Integrations](#integrations--hooks)). Columns include `book_name`,
`author`, `reference_number` (accession), `book_issue_date`, `book_return_date`, `reading_period`,
`book_status`, `reissue_count`, `due__days`.

### Library Management Settings (Single)

Global configuration.

| Field                             | Type     | Default          | Purpose                                                |
| --------------------------------- | -------- | ---------------- | ------------------------------------------------------ |
| `loan_period`                     | Int      | 30               | Loan length in **days** (used for due dates & reissue) |
| `enable_external_metadata_lookup` | Check    | 1                | Allow Google Books / Open Library ISBN lookup          |
| `enable_ai_fallback`              | Check    | 0                | Allow OpenAI cover extraction fallback                 |
| `openai_api_key`                  | Password | —                | Key for AI fallback                                    |
| `ai_model`                        | Data     | `gpt-5.4-mini`   | Model used for extraction                              |
| `default_take_home`               | Check    | 1                | Default `take_home` for new books                      |
| `branch_override_role`            | Data     | `System Manager` | Role allowed to issue across branches                  |

See the [ER diagram](flows.md#data-model) for relationships.

---

## Backend API

All public methods are `@frappe.whitelist()` in
[`services.py`](../library_management/services.py). Call them via `frappe.call("library_management.services.<name>", {...})`.

### Catalogue & metadata

| Method                                                                 | Args          | Returns / purpose                                                                                                                    |
| ---------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `get_user_library_branch()`                                            | —             | `{branch, is_ho}` for the logged-in user                                                                                             |
| `get_next_accession_number(branch=None)`                               | branch        | next sequential accession number                                                                                                     |
| `lookup_book_metadata_by_isbn(isbn)`                                   | isbn          | `{book_name, author, publisher, pages, …}` from Google Books / Open Library                                                          |
| `extract_book_metadata(front_image, back_image, branch, scanned_code)` | images / code | metadata via ISBN lookup or OpenAI fallback                                                                                          |
| `create_library_book_from_preview(payload)`                            | dict          | create a Library Books record from extracted metadata                                                                                |
| `save_library_books(rows, branch, room=None, book_shelf=None)`         | rows          | bulk create/update; **enforces Title/Author/Publisher/Accession**; auto-assigns accession if blank; generates QR; returns saved rows |
| `get_books_for_location(branch, room, book_shelf)`                     | location      | books at a shelf location                                                                                                            |

### QR codes

| Method                             | Args | Returns / purpose                                             |
| ---------------------------------- | ---- | ------------------------------------------------------------- |
| `generate_book_qr(book_name)`      | book | builds JSON payload + PNG data-URI, saves to the book         |
| `print_book_qr(book_name)`         | book | printable HTML for one book                                   |
| `print_book_qr_labels(book_names)` | list | printable A4 HTML, **3 labels per book** (accession required) |

QR payload requires `accession_number` **or** `isbn`. Image is a ~22mm PNG (via the `qrcode`
package) encoded as a `data:image/png;base64,…` URI.

### Resolution

| Method                                                           | Args                | Returns / purpose                                                                            |
| ---------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------- |
| `resolve_student(identifier, branch=None)`                       | ref-no / name       | student + `active_books` + `history` (`rows_for_student`) + `issued_count` + `overdue_count` |
| `resolve_book(identifier, branch=None, require_available=False)` | isbn/accession/name | one book or `{matches: [...]}`                                                               |
| `resolve_book_matches(identifier, branch, room, book_shelf)`     | identifier          | candidate copies with `can_issue` / `availability_label`                                     |

### Circulation

| Method                                                  | Args                                                   | Behaviour                                                                                                                                               |
| ------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `create_issue_transaction(student, books, branch=None)` | books=`[{library_book}]`                               | validates each via `_assert_can_issue`, creates a `Library Transactions`, sets copies `READING`, drops `available_quantity` to 0, updates student count |
| `return_books(student=None, books=None, branch=None)`   | books=`[{txn_book / library_book / accession_number}]` | marks matched READING rows `RETURNED` (today), restores `available_quantity=1` when a book is linked, updates student count                             |
| `reissue_books(student=None, books=None, branch=None)`  | same shape                                             | sets `due_date = today + loan_period`, increments `reissue_count`, keeps `READING`                                                                      |
| `update_all_due_days()`                                 | —                                                      | **daily scheduler**: recomputes `custom_number_of_books_issued` for students with active loans                                                          |

**Robust matching** (used by return/reissue): `_active_issue_rows(student)` selects READING rows for
the student in SQL (bounded, no global cap); `_row_is_selected()` matches on the transaction-book
**row id** (`txn_book`) or on `{library_book, isbn, accession_number}`. This lets the counter act on
legacy rows whose `library_book` link is NULL.

**Branch override**: issuing a book whose `branch` differs from the counter branch requires the
role named in `branch_override_role` (default `System Manager`).

---

## Controller logic

- **`LibraryTransactions`**
  ([library_transactions.py](../library_management/library_management/doctype/library_transactions/library_transactions.py)):
  `validate()` fills student details, normalizes any legacy single-book fields into the `books`
  table, and validates each child (availability, no duplicates, dates, status). `after_insert()` /
  `on_update()` run `update_book_inventory()` (sets `available_quantity` based on `READING`) and
  refresh the student's book count.
- **`rows_for_student(student)`**
  ([library_books_student_table.py](../library_management/library_management/doctype/library_books_student_table/library_books_student_table.py)):
  one SQL join over `Library Transaction Book` ↔ `Library Transactions` returning the full history
  (READING + RETURNED) with computed `reading_period`, `due__days`, and `reissue_count`. Reused by
  the Student onload hook **and** `resolve_student` (counter history).

---

## Integrations & hooks

From [`hooks.py`](../library_management/hooks.py):

- `after_install = library_management.setup.install.after_install` — on fresh install, runs the
  healing patches directly (Frappe marks `patches.txt` as already-applied on install).
- `after_migrate = library_management.migrate.after_migrate` — ensures the Student
  `custom_library_books` Table field exists with `is_virtual=0` and re-asserts it (defends against
  other apps flipping the flag).
- `doc_events["Student"]["onload"] = …populate_student_library_books_table` — fills
  `custom_library_books` live from `rows_for_student()` (Frappe v15 doesn't auto-fetch virtual child
  tables).
- `scheduler_events["daily"] = […update_all_due_days]` — keeps the student book count current.

The `custom_library_books` field is created/maintained in
[`migrate.py`](../library_management/migrate.py): Table field on Student, options
`Library Books Student Table`, `is_virtual=0`, inserted after `custom_number_of_books_issued`.

---

## Install & migration

`patches.txt` ordering:

```
[pre_model_sync]
heal_library_books_quantity_strings   # NA/NULL/0/non-numeric quantity -> valid int (before ALTER)
library_revamp_uat_fix                # drop legacy avail_quantity col, reconcile qty, fix virtual flag, clear stale snapshot

[post_model_sync]
migrate_library_transactions_to_books # legacy single-book transactions -> Library Transaction Book child rows
drop_legacy_doctypes                  # remove upstream demo doctypes (Library Transaction, Article, Library Member/Membership)
rename_library_book_intake_page       # delete stale 'library-book-intake' Page (renamed to add-library-books)
```

Notes:

- **Why heal quantities first**: legacy sites stored `quantity` as varchar with values like `'NA'`;
  Frappe's schema sync `ALTER … MODIFY int` crashes on those, so they are healed before the sync.
- **Virtual-child constraint**: Frappe v15 requires `parent.is_virtual == child.is_virtual`.
  `Student` is a regular doctype, so `Library Books Student Table` and the `custom_library_books`
  field are kept `is_virtual=0`; the data is filled live on `onload` instead.
- All patches are **idempotent** and safe to re-run.

See the [migration flow diagram](flows.md#install--upgrade-migration).

---

## External services

- **ISBN metadata**: Google Books and Open Library (HTTP GET), gated by
  `enable_external_metadata_lookup`.
- **AI cover extraction** (optional): OpenAI vision call, gated by `enable_ai_fallback` +
  `openai_api_key` + `ai_model`. Used by `extract_book_metadata` when ISBN lookup is insufficient.
- **QR**: the `qrcode` Python package; output embedded as a base64 PNG data-URI.

All three are best-effort and degrade gracefully (lookups that fail show a non-blocking alert in the
UI).

---

## Developer setup

```bash
# install into a bench
bench get-app <repo-url> --branch library-revamp
bench --site <site> install-app library_management

# day-to-day
bench build --app library_management      # rebuild page JS/CSS (no trailing slash)
bench --site <site> migrate               # sync doctypes + register reports + run patches
bench --site <site> reload-doc library_management report <report_name>   # register a single report

# code quality (pre-commit: ruff, eslint, prettier, pyupgrade)
cd apps/library_management && pre-commit install
```

- Page assets live in `page/<name>/<name>.{js,css,json}` and are bundled by `bench build`.
- Script Reports live in `report/<name>/<name>.{py,js,json}` and register on `migrate`.
- When `developer_mode` is off, run `bench build` after editing page JS/CSS for the browser to pick
  up changes (then hard-refresh).
