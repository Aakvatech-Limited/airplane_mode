// Copyright (c) 2026, Airborn108 and contributors
// For license information, please see license.txt
frappe.ui.form.on("Airline", {
    refresh(frm) {
        if (frm.doc.website) {
            let url = frm.doc.website;
            if (!/^https?:\/\//i.test(url)) {
                url = "https://" + url;
            }
            frm.add_web_link(url, __("Visit Website"));
        }
    }
});