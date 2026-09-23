import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum


def execute(filters=None):
    columns = get_columns()
    data = get_data()
    chart = get_chart(data)
    report_summary = get_summary(data)

    return columns, data, None, chart, report_summary


def get_columns():
    return [
        {
            "label": "Airline",
            "fieldname": "airline",
            "fieldtype": "Link",
            "options": "Airline",
            "width": 200
        },
        {
            "label": "Revenue",
            "fieldname": "revenue",
            "fieldtype": "Currency",
            "width": 200
        }
    ]


def get_data():
    Airline = DocType("Airline")
    Airplane = DocType("Airplane")
    AirplaneFlight = DocType("Airplane Flight")
    AirplaneTicket = DocType("Airplane Ticket")

    query = (
        frappe.qb.from_(Airline)
        .left_join(Airplane).on(Airplane.airline == Airline.name)
        .left_join(AirplaneFlight).on(AirplaneFlight.airplane == Airplane.name)
        .left_join(AirplaneTicket).on(
            (AirplaneTicket.flight == AirplaneFlight.name) &
            (AirplaneTicket.docstatus == 1)
        )
        .select(
            Airline.name.as_("airline"),
            Sum(AirplaneTicket.flight_price).as_("revenue")
        )
        .groupby(Airline.name)
    )

    data = query.run(as_dict=True)

    for row in data:
        row["revenue"] = row["revenue"] or 0

    return data


def get_chart(data):
    labels = [row["airline"] for row in data]
    values = [row["revenue"] for row in data]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"values": values}]
        },
        "type": "donut",
    }


def get_summary(data):
    total_revenue = sum(row["revenue"] for row in data)
    return [
        {
            "label": "Total Revenue",
            "value": total_revenue,
            "indicator": "Green",
            "datatype": "Currency"
        }
    ]
