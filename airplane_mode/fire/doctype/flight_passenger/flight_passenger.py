# Copyright (c) 2026, Airborn108 and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class FlightPassenger(Document):
	def before_save(self):
		self.full_name = " ".join(
			filter(None, [self.first_name, self.last_name])
		)