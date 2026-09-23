# Copyright (c) 2026, Airborn108 and contributors
# For license information, please see license.txt

import frappe
from frappe.website.website_generator import WebsiteGenerator


class AirplaneFlight(WebsiteGenerator):
	def on_submit(self):
		self.db_set("status", "Completed")

	def get_context(self, context):
		context.airline = frappe.db.get_value("Airplane", self.airplane, "airline")
		context.no_cache = 1