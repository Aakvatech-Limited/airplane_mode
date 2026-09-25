# Airplane Mode

Airplane Mode is a Frappe Framework application built as a practical learning project for airline, flight, ticketing, and payment workflows.

The app demonstrates how core Frappe concepts such as DocTypes, reports, notifications, print formats, web forms, APIs, and public pages can be combined into a working business application.

## Features

The project currently includes functionality around:

- Airline management
- Airplane management
- Airport management
- Flight and airplane flight records
- Passenger management
- Airplane ticket booking
- Ticket add-ons
- Source and destination airports
- M-Pesa payment handling and payment logs
- Public-facing landing page
- Reports
- Notifications
- Print Formats
- Web Forms

## Main DocTypes

Some of the main DocTypes currently included are:

- Airline
- Airplane
- Airport
- Airplane Flight
- Flight
- Flight Passenger
- Airplane Ticket
- Airplane Ticket Add On Item
- Airplane Ticket Add On Type
- Ticket Add On Selector
- Source Airport
- Destination Airport
- M-Pesa Payment Log

## Requirements

- Python 3.10 or later
- Frappe Framework
- Bench CLI

Frappe and its dependencies should normally be installed and managed through Bench.

## Installation

From your Frappe Bench directory:

```bash
bench get-app https://github.com/samsonmabula48-alt/airplane_mode.git
bench --site your-site-name install-app airplane_mode
```

Then migrate the site:

```bash
bench --site your-site-name migrate
```

For a local development environment:

```bash
bench start
```

## Project Structure

```text
airplane_mode/
├── airplane_mode/
│   ├── api/
│   ├── fire/
│   │   ├── doctype/
│   │   ├── notification/
│   │   ├── print_format/
│   │   ├── report/
│   │   └── web_form/
│   ├── public/
│   ├── templates/
│   ├── www/
│   └── hooks.py
├── pyproject.toml
└── README.md
```

The main Frappe module is `Fire`, which contains the application's DocTypes and related configuration.

## Development

Move into the application directory:

```bash
cd apps/airplane_mode
```

Install the configured pre-commit hooks:

```bash
pre-commit install
```

Run all configured checks before submitting changes:

```bash
pre-commit run --all-files
```

The repository uses development tooling including:

- Ruff
- ESLint
- Prettier
- PyUpgrade
- Frappe Semgrep rules
- pip-audit

## Contributing

Contributions and improvements are welcome.

When contributing:

- Keep changes focused.
- Follow Frappe development conventions.
- Add tests for new business logic where practical.
- Avoid committing credentials or environment-specific configuration.
- Clearly describe the purpose of the change in the pull request.

## License

This project is licensed under the [MIT License](license.txt).
