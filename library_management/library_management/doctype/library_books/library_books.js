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
			});
		});

		frm.add_custom_button(__("Print QR"), async () => {
			const r = await frappe.call({
				method: "library_management.services.print_book_qr_labels",
				args: { book_names: [frm.doc.name] },
				freeze: true,
				freeze_message: __("Preparing QR"),
			});
			if (r.message) {
				const blob = new Blob([r.message], { type: "text/html; charset=utf-8" });
				window.open(URL.createObjectURL(blob), "_blank");
			}
		});
	},

	qr_code_image(frm) {
		render_qr(frm);
	},
});

function render_qr(frm) {
	const field = frm.fields_dict.qr_code_image;
	if (!field || !field.$wrapper || !frm.doc.qr_code_image) {
		return;
	}
	const value = String(frm.doc.qr_code_image || "");
	let html = value;
	if (value.startsWith("data:image/")) {
		html = `<img src="${frappe.utils.escape_html(value)}" alt="${frappe.utils.escape_html(frm.doc.book_name || frm.doc.name)}" style="width:160px;height:160px;">`;
	}
	field.$wrapper.find(".control-value").html(`<div class="library-book-qr-preview">${html}</div>`);
}
