// Library Books — list view button: jump to the Add Library Books page
// for bulk multi-row entry by branch / room / shelf.
frappe.listview_settings["Library Books"] = {
	onload: function (listview) {
		listview.page.add_inner_button(__("Bulk Add Books"), function () {
			frappe.set_route("add-library-books");
		}, __("Actions"));
	},
};
