// Copyright (c) 2025, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Library Books", {
	refresh(frm) {
		if (frm.doc.__islocal) {
			return;
		}
		render_qr(frm);

		frm.add_custom_button(__("Generate QR"), () => {
			frappe.call({
				method: "library_management.services.generate_book_qr",
				args: { book_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Generating QR"),
				callback: (r) => {
					if (r.message) {
						frm.reload_doc();
					}
				},
				error: (error) => {
					frappe.msgprint({
						title: __("QR Generation Error"),
						message: __("This book does not have an accession number or ISBN number. It is required for QR generation."),
						indicator: "red"
					});
				}
			});
		});

		frm.add_custom_button(__("Print QR"), async () => {
			try {
				const r = await frappe.call({
					method: "library_management.services.print_book_qr_labels",
					args: { book_names: [frm.doc.name] },
					freeze: true,
					freeze_message: __("Preparing QR"),
				});
				if (r.message) {
					const blob = new Blob([r.message], { type: "text/html; charset=utf-8" });
					const url = URL.createObjectURL(blob);
					window.open(url, "_blank", "width=900,height=1000,menubar=yes,toolbar=yes");
				}
			} catch (error) {
				frappe.msgprint({
					title: __("QR Generation Error"),
					message: error.responseText || __("Unable to generate QR code. Please ensure the book has an accession number or ISBN."),
					indicator: "red"
				});
			}
		});
	},

	qr_code_image(frm) {
		render_qr(frm);
	},
});

function render_qr(frm) {
	if (!document.getElementById("library-book-qr-preview-css")) {
		const style = document.createElement("style");
		style.id = "library-book-qr-preview-css";
		style.textContent = `
			[data-fieldname="qr_code_image"] .control-value,
			[data-fieldname="qr_code_image"] .ace-editor-target,
			[data-fieldname="qr_code_image"] > .icon-btn { display: none !important; }
			.library-book-qr-preview img { width: 140px !important; height: 140px !important; display: block; }
		`;
		document.head.appendChild(style);
	}
	const field = frm.fields_dict.qr_code_image;
	if (!field || !field.$wrapper || !frm.doc.qr_code_image) {
		return;
	}
	const value = String(frm.doc.qr_code_image || "");
	let src = "";
	if (value.startsWith("data:image/")) {
		src = value;
	} else {
		const match = value.match(/<img[^>]+src=["']([^"']+)["']/i);
		if (match) {
			src = match[1];
		}
	}
	if (!src) {
		return;
	}
	const alt = frappe.utils.escape_html(frm.doc.book_name || frm.doc.name);
	const img = `<img src="${frappe.utils.escape_html(src)}" alt="${alt}">`;
	const $wrapper = field.$wrapper;
	let $preview = $wrapper.find(".library-book-qr-preview");
	if (!$preview.length) {
		$preview = $(`<div class="library-book-qr-preview" style="margin-top:6px;"></div>`);
		$wrapper.append($preview);
	}
	$preview.html(img);
}
