// Copyright (c) 2026, Frappe and contributors
// For license information, please see license.txt

frappe.query_reports["Overdue Books"] = {
	filters: [
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "School" },
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
