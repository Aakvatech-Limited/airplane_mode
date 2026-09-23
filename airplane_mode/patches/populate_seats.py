import frappe
import random


def execute():
    tickets = frappe.get_all("Airplane Ticket", pluck="name")

    for ticket_name in tickets:
        seat = f"{random.randint(1, 99)}{random.choice('ABCDE')}"

        frappe.db.set_value(
            "Airplane Ticket",
            ticket_name,
            "seat",
            seat
        )