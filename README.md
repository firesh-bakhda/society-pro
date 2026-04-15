
# Society Pro

Society Pro is a desktop membership and billing system built with Python, CustomTkinter, and SQLite.

It helps societies and community organizations manage member registration, fee payments, renewals, receipt generation, reporting, and administrative settings from a single GUI app.

## Highlights

- Member registration with profile details, region-aware global contact fields, and initial payment selection.
- Renewal workflow with eligibility rules (revoked members and Life Members are excluded).
- Bulk member import from Excel using a guided template with strict dropdown validation.
- Receipt generation as professional PDF (single and consolidated).
- Member lifecycle support: view details, edit profile, revoke membership.
- Export member details and payment records to Excel.
- Statistics dashboard with KPI cards and charts.
- Admin settings for society profile, logo, fee configuration, and dynamic member types.

## Tech Stack

- Python 3.10+
- CustomTkinter (UI)
- SQLite (local database)
- FPDF2 (PDF receipts)
- OpenPyXL (Excel import/export)
- TkCalendar (date input)
- Nuitka (standalone executable build)

## Project Structure

```text
society-pro/
|- society-membership.py      # Main desktop application
|- pyproject.toml             # Project metadata and dependencies
|- build_nuitka.bat           # Windows Nuitka build script
|- build_nuitka.sh            # Bash Nuitka build script
|- RELEASE_v1.0.md            # Release notes
|- LICENSE
```

## Installation

### Setup: `uv` (recommended)

```bash
uv venv --python 3.10
uv sync
```

## Run the App

```bash
. .venv/Scripts/activate
python society-membership.py
```

On first run, the app creates a local SQLite database file:

- `society_pro_v2.db`

The app also auto-initializes default configuration values such as fee types, member types, and admin settings.

## Main Modules in the UI

- Register Member
- Renew / Pay Fees
- View Member Details
- Generate Receipts
- Payment Records
- Statistics
- Admin Settings
- About

## Core Workflows

### 1. Register Member

- Capture profile, address, and global ID/mobile/home values.
- Select initial payment package:
	- Entrance Fee
	- Entrance Fee + Annual Subscription
	- Life Membership
- Save member and payment records.
- Generate receipt PDF immediately.

### 2. Renew Membership

- Select an eligible member.
- Choose renewal fee type.
- Record payment and print receipt.

### 3. Bulk Import from Excel

- Open the built-in template from the registration screen.
- Fill rows using allowed values for Profession and Member Type.
- Import members in one action.
- Duplicate handling is case-insensitive and rows with existing active records are skipped.

### 4. Member Operations

- Search and view enriched member table (payments count, total paid, last payment).
- Edit selected member profile fields.
- Revoke membership with timestamp tracking.
- Export table to Excel.

### 5. Reporting and Receipts

- View payment logs and export to Excel.
- Generate consolidated PDF receipts for selected payment rows.
- Use dashboard statistics for distribution and trend monitoring.

## Build Standalone Executable (Windows)

Use the provided batch script:

```bat
build_nuitka.bat
```

This script:

- Validates `.venv` Python environment.
- Installs Nuitka build tooling (`nuitka`, `ordered-set`, `zstandard`) via `uv`.
- Produces standalone executable output in:

```text
build/society-membership.dist/SocietyPro.exe
```

## Data Model (SQLite)

Database file: `society_pro_v2.db`

Primary tables:

- `members`
- `payments`
- `fee_config`
- `member_types`
- `admin_settings`

The app includes startup migration logic for older databases (for example adding newer columns like revocation and membership timestamp fields when missing).

## Troubleshooting

- If date picker widgets do not load, ensure `tkcalendar` is installed.
- If PDF generation fails, verify `fpdf2` is installed in the active virtual environment.
- If Excel import/export fails, verify `openpyxl` is installed.
- If build fails, ensure `uv` is available in PATH and `.venv` exists.

## License

This project uses the Community Edition License in [LICENSE](LICENSE).

Summary:

- Personal, educational, and societal non-commercial use is permitted.
- Commercial redistribution requires written permission from the author.

## Author

- Firesh Kishor Kumar (Firesh Bakhda)
- Contact: firesh@gmail.com
