<div align="center">

# 📚 Library Management

**A school-library circulation system built on [Frappe](https://frappeframework.com/) v15.**

Issue, return and renew books at a fast counter; bulk-catalogue stock with ISBN auto-lookup and QR
labels; track every student's borrowing history; and run circulation & inventory reports.

</div>

---

## What it is

Library Management turns a Frappe/ERPNext site into a multi-branch school library system. It is
tightly integrated with the **Student** record (from the Education module), so a student's borrowed
books appear right on their profile, and the librarian works from a single, scanner-friendly
**Library Counter**.

## ✨ Key features

- **Fast circulation desk** — fetch a student, scan books, and **issue / return / reissue** in
  batches.
- **Multi-book transactions** — one transaction can hold many copies.
- **Reissue (renew)** — extend a due date by the loan period without returning the book; renewals
  are counted.
- **Borrowing history** — full issue/return history on the counter and on the Student form.
- **Bulk book intake** — maintain books per branch/room/shelf with inline editing.
- **ISBN auto-lookup** — fetch title/author/publisher/pages from Google Books / Open Library, with
  an **optional AI cover-extraction** fallback.
- **QR codes** — generate per-book QR codes and print **3 labels per book**.
- **Inventory tracking** — quantity / available / issued, per branch and shelf.
- **5 built-in reports** — Book Issue Register, Overdue Books, Most Issued Books, Library Stock
  Summary, Unavailable Books.

## 📸 Screenshots

| Library Counter                                     | Add Library Books                               |
| --------------------------------------------------- | ----------------------------------------------- |
| ![Library Counter](docs/assets/library-counter.png) | ![Add Library Books](docs/assets/add-books.png) |

## 🎬 Feature demos

| Issue books                                        | Reissue (renew)                                        | Return books                                         |
| -------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------- |
| ![Issue](docs/assets/recordings/feature-issue.gif) | ![Reissue](docs/assets/recordings/feature-reissue.gif) | ![Return](docs/assets/recordings/feature-return.gif) |

| Issue / Return history                                 | Reports menu                                           | Bulk book intake                                           |
| ------------------------------------------------------ | ------------------------------------------------------ | ---------------------------------------------------------- |
| ![History](docs/assets/recordings/feature-history.gif) | ![Reports](docs/assets/recordings/feature-reports.gif) | ![Add Books](docs/assets/recordings/feature-add-books.gif) |

| ISBN metadata auto-fill                                        | QR label printing                                           |
| -------------------------------------------------------------- | ----------------------------------------------------------- |
| ![ISBN auto-fill](docs/assets/recordings/feature-metadata.gif) | ![QR printing](docs/assets/recordings/feature-qr-print.gif) |

## 🚀 Quick start

Requirements: a [Frappe Bench](https://github.com/frappe/bench) running **Frappe v15**, **Python
≥ 3.10**, and the **[Education](https://github.com/frappe/education)** app — it provides the
`Student` and `School` doctypes this app builds on, so install it first. The `qrcode` Python
package is installed automatically.

```bash
cd $PATH_TO_YOUR_BENCH

# 1) Education first — provides Student + School
bench get-app https://github.com/frappe/education
bench --site <your-site> install-app education

# 2) Then this app
bench get-app https://github.com/WalnutAppSuite/library_management --branch library-revamp
bench --site <your-site> install-app library_management
bench --site <your-site> migrate     # syncs doctypes and registers the reports
```

Then open **Library Counter** (`/app/library-counter`) to start, and set your **Loan Period** in
**Library Management Settings**.

## 📖 Documentation

| Guide                                              | For whom                                                   |
| -------------------------------------------------- | ---------------------------------------------------------- |
| [User Guide](docs/user-guide.md)                   | Librarians & admins — how to run the desk, intake, reports |
| [Technical Reference](docs/technical-reference.md) | Developers — data model, API, hooks, migrations            |
| [Reports](docs/reports.md)                         | Both — the five reports, filters and sources               |
| [Flows & Diagrams](docs/flows.md)                  | Both — Mermaid diagrams of every flow + the data model     |

## ⚙️ Configuration

Configure behaviour in **Library Management Settings** (a Single doctype): loan period, external
metadata lookup, AI fallback (key/model), default take-home, and the branch-override role. See the
[User Guide → Settings](docs/user-guide.md#settings-for-admins).

## 🤝 Contributing

This app uses `pre-commit` for formatting and linting. Please
[install pre-commit](https://pre-commit.com/#installation) and enable it:

```bash
cd apps/library_management
pre-commit install
```

Configured tools: **ruff**, **eslint**, **prettier**, **pyupgrade**. See the
[Technical Reference → Developer setup](docs/technical-reference.md#developer-setup) for the dev
workflow (`bench build`, `migrate`, `reload-doc`).

## 📄 License

[MIT](license.txt)
