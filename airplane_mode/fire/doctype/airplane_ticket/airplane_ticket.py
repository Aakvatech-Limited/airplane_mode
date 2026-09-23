
# Copyright (c) 2026, Airborn108 and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import random


class AirplaneTicket(Document):

    def before_insert(self):
        # Automatically assign a seat based on the selected Seat Position
        if self.seat_position == "Window":
            possible_seats = [
                f"{number}{letter}"
                for number in range(1, 100)
                for letter in ["A", "F"]
            ]

        elif self.seat_position == "Aisle":
            possible_seats = [
                f"{number}{letter}"
                for number in range(1, 100)
                for letter in ["C", "D"]
            ]

        else:
            frappe.throw(
                "Please select a Seat Position: Window or Aisle."
            )

        # Get seats already occupied on this flight
        occupied_seats = frappe.get_all(
            "Airplane Ticket",
            filters={
                "flight": self.flight,
                "docstatus": ["!=", 2]
            },
            pluck="seat"
        )

        # Remove already occupied seats
        available_seats = [
            seat for seat in possible_seats
            if seat not in occupied_seats
        ]

        # Stop booking if no seat is available for the selected position
        if not available_seats:
            frappe.throw(
                f"No {self.seat_position} seats are available on this flight."
            )

        # Automatically assign one available seat
        self.seat = random.choice(available_seats)

    def validate(self):
        unique_addons = []

        self.check_seat_availability()

        # Remove duplicate add-ons
        for addon in self.add_ons:
            if addon.item not in [d.item for d in unique_addons]:
                unique_addons.append(addon)

        self.add_ons = unique_addons

        # Calculate total amount
        self.total_amount = self.flight_price

        for addons in self.add_ons:
            self.total_amount += addons.amount

    def before_submit(self):
        if self.status != "Boarded":
            frappe.throw(
                "Airplane ticket can only be submitted when the status is Boarded"
            )

    def check_seat_availability(self):
        flight = frappe.get_doc("Airplane Flight", self.flight)

        capacity = frappe.db.get_value(
            "Airplane",
            flight.airplane,
            "capacity"
        )

        existing_tickets = frappe.db.count(
            "Airplane Ticket",
            filters={
                "flight": self.flight,
                "name": ["!=", self.name],
                "docstatus": ["!=", 2],
            }
        )

        if existing_tickets + 1 > capacity:
            frappe.throw(
                f"Cannot book this ticket. Flight {self.flight} "
                f"has reached its maximum capacity of {capacity} seats."
            )

    def before_save(self):
        self.full_name = " ".join(
            filter(None, [self.passenger, self.last_name])
        )

    def on_submit(self):
        customer_name = self.full_name or " ".join(
            filter(None, [self.passenger, self.last_name])
        )

        if not customer_name:
            frappe.throw("Passenger name is required before creating the Sales Invoice.")

        if self.sales_invoice:
            return

        # Works whether your custom field is called airplane_ticket or custom_airplane_ticket
        item_meta = frappe.get_meta("Sales Invoice Item")
        ticket_field = (
            "custom_airplane_ticket"
            if item_meta.has_field("custom_airplane_ticket")
            else "airplane_ticket"
        )

        existing_invoice = frappe.db.get_value(
            "Sales Invoice Item", {ticket_field: self.name}, "parent"
        )
        if existing_invoice:
            self.db_set("sales_invoice", existing_invoice)
            return

        customer = frappe.db.get_value(
            "Customer", {"customer_name": customer_name}, "name"
        )

        if not customer:
            customer_doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "All Territories"
            })
            customer_doc.insert(ignore_permissions=True)
            customer = customer_doc.name

        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": customer,
            "items": [{
                "item_code": "Airplane Flight Ticket",
                "qty": 1,
                "rate": self.total_amount,
                ticket_field: self.name
            }]
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()

        # Link the invoice back to the ticket so the checkout page can find it
        self.db_set("sales_invoice", invoice.name)