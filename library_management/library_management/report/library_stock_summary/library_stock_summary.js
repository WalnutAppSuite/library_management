// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.query_reports["Library Stock Summary"] = {
	filters: [
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "School" },
		{ fieldname: "room", label: __("Room"), fieldtype: "Link", options: "Room" },
		{ fieldname: "book_shelf", label: __("Shelf"), fieldtype: "Data" },
		{ fieldname: "only_low_stock", label: __("Only Out of Stock"), fieldtype: "Check" },
	],
};
