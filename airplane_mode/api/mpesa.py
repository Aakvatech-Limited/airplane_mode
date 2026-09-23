# Copyright (c) 2026
# M-Pesa (Vodacom Open API) C2B integration for airplane_mode

import base64

import frappe
import requests
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _get_settings():
	conf = frappe.conf
	settings = {
		"api_key": conf.get("mpesa_api_key"),
		"public_key": conf.get("mpesa_public_key"),
		"service_provider_code": conf.get("mpesa_service_provider_code"),
		"base_url": conf.get("mpesa_base_url"),
		"country": conf.get("mpesa_country", "TZN"),
		"currency": conf.get("mpesa_currency", "TZS"),
		"session_ttl_sec": int(conf.get("mpesa_session_ttl_sec", 3300)),
	}
	missing = [k for k in ("api_key", "public_key", "service_provider_code", "base_url") if not settings[k]]
	if missing:
		frappe.throw(
			"M-Pesa is not fully configured. Missing site_config keys: {}".format(", ".join(
				"mpesa_" + m for m in missing
			))
		)
	return settings


def _normalize_msisdn(number: str) -> str:
	"""Convert 0746873794, +255746873794 or 746873794 into 255746873794."""
	n = "".join(ch for ch in str(number) if ch.isdigit())  # keep digits only

	if n.startswith("255"):
		pass
	elif n.startswith("0"):
		n = "255" + n[1:]
	elif len(n) == 9:
		n = "255" + n

	if not (n.startswith("255") and len(n) == 12):
		frappe.throw("Please enter a valid phone number, e.g. 0746873794 or 255746873794.")

	return n


def _encrypt_api_key(api_key: str, public_key_pem: str) -> str:
	"""RSA/ECB/PKCS1Padding encrypt, matching Vodacom's requirements."""
	clean_key = (
		public_key_pem.replace("-----BEGIN PUBLIC KEY-----", "")
		.replace("-----END PUBLIC KEY-----", "")
		.replace("\n", "")
		.replace("\r", "")
		.strip()
	)

	chunks = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
	formatted_key_body = "\n".join(chunks)

	pem_string = f"-----BEGIN PUBLIC KEY-----\n{formatted_key_body}\n-----END PUBLIC KEY-----\n"

	public_key = load_pem_public_key(pem_string.encode())
	encrypted = public_key.encrypt(api_key.encode(), asym_padding.PKCS1v15())
	return base64.b64encode(encrypted).decode()


def _get_session_key(settings: dict) -> str:
	cached = frappe.cache().get_value("mpesa_session_key")
	if cached:
		return cached.decode('utf-8') if isinstance(cached, bytes) else str(cached)

	encrypted_key = _encrypt_api_key(settings["api_key"], settings["public_key"])
	resp = requests.get(
		f"{settings['base_url']}/getSession/",
		headers={
			"Authorization": f"Bearer {encrypted_key}",
			"Origin": "https://openapi.m-pesa.com",
			"Content-Type": "application/json"
		},
		timeout=30,
	)
	data = resp.json()
	session_id = data.get("output_SessionID")
	if not session_id:
		frappe.throw(f"Could not obtain M-Pesa session: {data}")

	frappe.cache().set_value("mpesa_session_key", str(session_id), expires_in_sec=settings["session_ttl_sec"])
	return str(session_id)


@frappe.whitelist()
def initiate_payment(sales_invoice: str, customer_msisdn: str):
	"""Kick off a C2B payment request for a Sales Invoice."""
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)

	if invoice.docstatus != 1:
		frappe.throw("Sales Invoice must be submitted before requesting payment.")
	if invoice.outstanding_amount <= 0:
		frappe.throw("This invoice has no outstanding amount to pay.")

	# Fix the phone format BEFORE anything is logged or sent
	customer_msisdn = _normalize_msisdn(customer_msisdn)

	settings = _get_settings()
	conversation_id = frappe.generate_hash(length=12).upper()

	log = frappe.get_doc({
		"doctype": "MPesa Payment Log",
		"conversation_id": conversation_id,
		"sales_invoice": invoice.name,
		"msisdn": customer_msisdn,
		"amount": invoice.outstanding_amount,
		"status": "Pending",
	}).insert(ignore_permissions=True)

	raw_session_id = _get_session_key(settings)
	encrypted_bearer_token = _encrypt_api_key(raw_session_id, settings["public_key"])
	clean_amount = str(int(float(invoice.outstanding_amount)))

	payload = {
		"input_Amount": clean_amount,
		"input_Country": settings["country"],
		"input_Currency": settings["currency"],
		"input_CustomerMSISDN": customer_msisdn,
		"input_ServiceProviderCode": settings["service_provider_code"],
		"input_TransactionReference": "REFTZ",
		"input_ThirdPartyConversationID": conversation_id,
		"input_PurchasedItemsDesc": "Airfare",
	}

	resp = requests.post(
		f"{settings['base_url']}/c2bPayment/singleStage/",
		json=payload,
		headers={
			"Authorization": f"Bearer {encrypted_bearer_token}",
			"Origin": "https://openapi.m-pesa.com",
			"Content-Type": "application/json",
		},
		timeout=30,
	)

	data = resp.json() if resp.content else {}
	log.db_set("raw_response", frappe.as_json(data))

	if data.get("output_ResponseCode") not in ("INS-0", "0"):
		log.db_set("status", "Failed")
		frappe.log_error(message=frappe.as_json(data), title="M-Pesa Detailed Rejection")
		frappe.throw(f"M-Pesa rejected the request. Server payload returned: {data}")

	return {
		"conversation_id": conversation_id,
		"message": "Payment request sent. Ask the customer to check their phone to approve it.",
	}


@frappe.whitelist(allow_guest=True)
def callback():
	"""Receives M-Pesa's async C2B result."""
	data = frappe.request.get_json(force=True) or {}
	frappe.log_error(message=frappe.as_json(data), title="M-Pesa Callback Raw Data")

	# Optional shared secret: add ?token=XXXX to the callback URL you gave Vodacom
	expected = frappe.conf.get("mpesa_callback_token")
	if expected and frappe.form_dict.get("token") != expected:
		frappe.local.response["http_status_code"] = 403
		return {"output_ResponseCode": "INS-6", "output_ResponseDesc": "Forbidden"}

	conversation_id = (
		data.get("input_ThirdPartyConversationID")
		or data.get("output_ThirdPartyConversationID")
		or data.get("ThirdPartyConversationID")
	)
	result_code = str(
		data.get("input_ResultCode") or data.get("output_ResponseCode") or data.get("ResponseCode") or ""
	)
	transaction_id = (
		data.get("input_TransactionID") or data.get("output_TransactionID") or data.get("TransactionID")
	)

	# No fallback guessing: the reference must match a Pending log
	if not conversation_id:
		return {"output_ResponseCode": "INS-6", "output_ResponseDesc": "Unknown Reference"}

	log_name = frappe.db.get_value(
		"MPesa Payment Log", {"conversation_id": conversation_id, "status": "Pending"}
	)
	if not log_name:
		return {"output_ResponseCode": "INS-6", "output_ResponseDesc": "Unknown Reference"}

	log = frappe.get_doc("MPesa Payment Log", log_name)
	log.db_set("raw_response", frappe.as_json(data))
	if transaction_id:
		log.db_set("transaction_id", str(transaction_id))

	# Only pay the invoice if M-Pesa says the payment succeeded
	if result_code not in ("INS-0", "0"):
		log.db_set("status", "Failed")
		frappe.db.commit()
		return {"output_ResponseCode": "INS-0", "output_ResponseDesc": "Received"}

	_mark_invoice_paid(log.sales_invoice, transaction_id)
	log.db_set("status", "Success")

	frappe.db.commit()
	return {"output_ResponseCode": "INS-0", "output_ResponseDesc": "Received Successfully"}


def _send_ticket_email(ticket_name: str):
	"""Email the passenger their ticket PDF after payment."""
	original_user = frappe.session.user
	try:
		# The callback runs as Guest, so render/send as Administrator
		frappe.set_user("Administrator")

		doc = frappe.get_doc("Airplane Ticket", ticket_name)
		if not doc.email:
			return

		print_format = "Airplane Ticket Boarding Pass"
		if not frappe.db.exists("Print Format", print_format):
			print_format = None  # falls back to the standard format

		# Build the PDF manually so we can pass wkhtmltopdf options
		# (attach_print() in this Frappe version does not accept pdf_options)
		html = frappe.get_print(
			"Airplane Ticket",
			doc.name,
			print_format=print_format,
			letterhead=None,
		)
		pdf_content = frappe.utils.pdf.get_pdf(
			html,
			options={
				"load-error-handling": "ignore",
				"load-media-error-handling": "ignore",
			},
		)
		pdf = {
			"fname": f"{doc.name}.pdf",
			"fcontent": pdf_content,
		}

		frappe.sendmail(
			recipients=[doc.email],
			subject=f"Your Flight Ticket - {doc.flight}",
			message=(
				f"<p>Dear {doc.full_name or 'Passenger'},</p>"
				f"<p>Thank you for your payment. Your booking is confirmed.</p>"
				f"<p><b>Flight:</b> {doc.flight}<br>"
				f"<b>Seat:</b> {doc.seat}<br>"
				f"<b>Ticket No:</b> {doc.name}</p>"
				f"<p>Your ticket is attached as a PDF. Have a safe flight!</p>"
			),
			attachments=[pdf],
			reference_doctype="Airplane Ticket",
			reference_name=doc.name,
			now=True,
		)
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title="Ticket Email Failed")
	finally:
		frappe.set_user(original_user)


def _mark_invoice_paid(sales_invoice: str, transaction_id: str):
	"""Reconcile the Sales Invoice after a successful M-Pesa payment."""

	try:
		invoice = frappe.get_doc("Sales Invoice", sales_invoice)

		if invoice.docstatus != 1:
			frappe.throw("Sales Invoice must be submitted before payment.")

		if invoice.outstanding_amount <= 0:
			return

		# Temporarily perform the accounting operation as Administrator.
		original_user = frappe.session.user
		frappe.set_user("Administrator")

		try:
			from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

			pe = get_payment_entry(
				"Sales Invoice",
				sales_invoice,
				bank_account="M-Pesa - A"
			)

			pe.mode_of_payment = "M-Pesa"
			pe.reference_no = transaction_id or sales_invoice
			pe.reference_date = frappe.utils.nowdate()

			pe.insert(ignore_permissions=True)
			pe.submit()

		finally:
			frappe.set_user(original_user)

	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="M-Pesa Accounting Failed"
		)
		raise

	try:
		frappe.log_error(message=f"invoice={sales_invoice}", title="MPESA_DEBUG_1_entered_ticket_block")

		linked_tickets = frappe.get_all(
			"Airplane Ticket",
			filters={"sales_invoice": sales_invoice},
			fields=["name"]
		)

		frappe.log_error(message=f"found {len(linked_tickets)} tickets: {[t['name'] for t in linked_tickets]}", title="MPESA_DEBUG_2_linked_tickets")

		for ticket_info in linked_tickets:
			frappe.db.set_value(
				"Airplane Ticket",
				ticket_info["name"],
				"status",
				"Paid"
			)
			# Run in a background worker instead of inline, so a slow PDF/email
			# step can never block or get killed by the web request timeout.
			frappe.enqueue(
				"airplane_mode.api.mpesa._send_ticket_email",
				queue="short",
				ticket_name=ticket_info["name"],
				enqueue_after_commit=True,
			)

		frappe.publish_realtime(
			event="mpesa_payment_success",
			message={"sales_invoice": sales_invoice},
			after_commit=True
		)

	except Exception:
		frappe.log_error(
			message=frappe.get_traceback(),
			title="M-Pesa Custom Ticket Status Failure"
		)