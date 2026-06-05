# Flows & Diagrams

This page collects the end-to-end flows of the Library Management app as
[Mermaid](https://mermaid.js.org/) diagrams (they render natively on GitHub) plus short step
lists. It is useful for both readers who want the big picture and developers who want to trace the
code.

- [Data model (ER diagram)](#data-model)
- [Issue books](#issue-books)
- [Return books](#return-books)
- [Reissue / renew books](#reissue--renew-books)
- [Book intake + QR labels](#book-intake--qr-labels)
- [Student borrowing history](#student-borrowing-history)
- [Install / upgrade migration](#install--upgrade-migration)

---

## Data model

```mermaid
erDiagram
    STUDENT ||--o{ LIBRARY_TRANSACTIONS : "borrows via"
    LIBRARY_TRANSACTIONS ||--|{ LIBRARY_TRANSACTION_BOOK : "contains"
    LIBRARY_BOOKS ||--o{ LIBRARY_TRANSACTION_BOOK : "issued as"
    SCHOOL ||--o{ LIBRARY_BOOKS : "branch of"
    STUDENT ||--o{ LIBRARY_BOOKS_STUDENT_TABLE : "history shown on form"

    LIBRARY_BOOKS {
        string name PK "B.######"
        string isbn
        string book_name
        string accession_number
        string author
        string status "Active/Inactive/Discontinued"
        link branch "School"
        int quantity
        int available_quantity
        check take_home
        longtext qr_code_payload
    }
    LIBRARY_TRANSACTIONS {
        string name PK
        link student "Student"
        data branch
        table books "Library Transaction Book"
    }
    LIBRARY_TRANSACTION_BOOK {
        link library_book "Library Books"
        date issue_date
        date due_date
        date return_date
        select book_status "READING/RETURNED"
        int reissue_count
    }
    LIBRARY_BOOKS_STUDENT_TABLE {
        data book_name
        date book_issue_date
        datetime book_return_date
        select book_status
        int reissue_count
        data due__days
    }
```

> `Library Management Settings` is a Single doctype (global config) and is not part of the relations.

---

## Issue books

A librarian issues one or more copies to a student from the **Library Counter**.

```mermaid
sequenceDiagram
    actor Librarian
    participant UI as Library Counter (JS)
    participant API as services.py
    participant DB as Database

    Librarian->>UI: Fetch student (ref no / link)
    UI->>API: resolve_student(identifier, branch)
    API-->>UI: student + active_books + history + counts
    Librarian->>UI: Scan ISBN / accession, "Find Book"
    UI->>API: resolve_book_matches(identifier, branch)
    API-->>UI: matching copies (can_issue, availability)
    Librarian->>UI: Add books, "Issue Books"
    UI->>API: create_issue_transaction(student, books, branch)
    API->>API: resolve_book(require_available) + _assert_can_issue
    API->>DB: insert Library Transactions (+ child rows, READING)
    API->>DB: available_quantity = 0 (after_insert inventory)
    API->>DB: update Student.custom_number_of_books_issued
    API-->>UI: transaction
    Note over UI,API: counter refreshes via resolve_student(...)
```

**Rules enforced** (`_assert_can_issue` in `services.py`): book `status == "Active"`,
`take_home == 1`, branch matches the counter branch (unless the user has the **Branch Override
Role**), and `available_quantity > 0`.

---

## Return books

```mermaid
flowchart TD
    A[Select active books, Return Selected] --> B[return_books student, books]
    B --> C[_active_issue_rows: READING rows for this student]
    C --> D{Row matches?<br/>by txn_book id OR<br/>library_book/isbn/accession}
    D -- no --> C
    D -- yes --> E[book_status = RETURNED<br/>return_date = today]
    E --> F{library_book set?}
    F -- yes --> G[available_quantity = 1]
    F -- no --> H[skip availability<br/>legacy NULL-book row]
    G --> I[update Student book count]
    H --> I
    I --> J[refresh counter]
```

The matching scan is **scoped to the student in SQL** so it is correct and bounded (no global
row cap). Matching by the transaction-book **row id** lets the counter return legacy rows that have
no linked `Library Books` record.

---

## Reissue / renew books

Same selection + scan as Return, but the book **stays issued** — only the due date moves.

```mermaid
flowchart TD
    A[Select active books, Reissue Selected] --> B[reissue_books student, books]
    B --> C[_active_issue_rows: READING rows for this student]
    C --> D{Row matches?}
    D -- yes --> E[due_date = today + loan_period]
    E --> F[reissue_count = reissue_count + 1]
    F --> G[book_status stays READING<br/>availability unchanged]
    G --> H[refresh counter + history]
```

`loan_period` comes from **Library Management Settings** (default 30 days).

---

## Book intake + QR labels

Bulk add/maintain books on the **Add Library Books** page.

```mermaid
sequenceDiagram
    actor Librarian
    participant UI as Add Library Books (JS)
    participant API as services.py
    participant Ext as Google Books / Open Library / OpenAI

    Librarian->>UI: Pick Branch / Room / Shelf
    Librarian->>UI: Load Books or Add Row
    Librarian->>UI: Type ISBN (blur)
    UI->>API: lookup_book_metadata_by_isbn(isbn)
    API->>Ext: fetch metadata (if enabled)
    Ext-->>API: title, author, publisher, pages
    API-->>UI: prefill empty fields
    Librarian->>UI: Save (Title/Author/Publisher/Accession required)
    UI->>API: save_library_books(rows, branch, room, shelf)
    API->>API: validate mandatory fields, normalize, accession
    API->>API: generate_book_qr (per book)
    API-->>UI: saved rows (QR Ready)
    Librarian->>UI: Print Selected QR
    UI->>API: print_book_qr_labels(book_names)
    API-->>UI: printable HTML (3 labels/book)
```

---

## Student borrowing history

The Student form shows a read-only **Library Books** table, filled live on form load.

```mermaid
flowchart LR
    A[Open Student form] --> B[onload hook]
    B --> C[populate_student_library_books_table]
    C --> D[rows_for_student: JOIN<br/>Library Transaction Book + Library Transactions]
    D --> E[set custom_library_books child table]
```

The same `rows_for_student()` query powers the **Issue/Return History** table on the Library
Counter (returned via `resolve_student`).

---

## Install / upgrade migration

```mermaid
flowchart TD
    subgraph Fresh install
      I1[after_install hook] --> I2[run heal/UAT/rename patches directly]
    end
    subgraph bench migrate
      M0[pre_model_sync] --> M1[heal_library_books_quantity_strings<br/>NA/NULL/0 quantity -> valid int]
      M1 --> M2[library_revamp_uat_fix<br/>drop legacy column, reconcile qty, fix virtual flag]
      M2 --> M3[schema sync]
      M3 --> M4[post_model_sync]
      M4 --> M5[migrate_library_transactions_to_books<br/>legacy single-book -> child rows]
      M5 --> M6[drop_legacy_doctypes]
      M6 --> M7[rename_library_book_intake_page]
    end
    M3 --> AM[after_migrate: ensure custom_library_books on Student, is_virtual=0]
```

See [technical-reference.md](technical-reference.md#install--migration) for what each patch does and
why the `is_virtual=0` constraint matters in Frappe v15.
