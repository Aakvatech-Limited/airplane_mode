import frappe

SUBMIT_STATUS = "Boarded"   # must match your before_submit rule


@frappe.whitelist()
def create_invoice(ticket):
    doc = frappe.get_doc("Airplane Ticket", ticket)

    if doc.sales_invoice:
        return doc.sales_invoice

    if doc.docstatus == 0:
        doc.status = SUBMIT_STATUS
        doc.flags.ignore_permissions = True
        doc.submit()          # on_submit creates the invoice

    doc.reload()
    if not doc.sales_invoice:
        frappe.throw("Ticket was submitted but no Sales Invoice was created.")

    return doc.sales_invoice