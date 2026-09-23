import frappe

def get_context(context):
    context.title = "Book Your Flight"
    context.no_cache = 1  # disable caching while developing

    # Example: pull dynamic data, e.g. popular routes/destinations
    context.destinations = frappe.get_all(
        "Destination",  # your own doctype, if you make one
        fields=["city", "country", "image"],
        limit=6
    )

@frappe.whitelist(allow_guest=True)
def submit_booking(name, email, phone, origin, destination, travel_date):
    """Called from JS when the form is submitted"""
    doc = frappe.get_doc({
        "doctype": "Flight Booking",  # you'd create this doctype
        "customer_name": name,
        "email": email,
        "phone": phone,
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "status": "Pending"
    })
    doc.insert(ignore_permissions=True)
    return {"success": True, "booking_id": doc.name}