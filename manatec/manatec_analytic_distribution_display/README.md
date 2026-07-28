# manaTec Analytic Distribution Display

This module provides a reusable abstract mixin that translates Odoo's JSON-based `analytic_distribution` (Kostenverteilung) field into a human-readable string representation, sorted by analytic plan and percentage, along with custom decimal precision configuration.

## Features

### Analytic Distribution Mixin (`analytic.distribution.display.mixin`)
- Automatically parses `analytic_distribution` (Kostenverteilung) JSON data on records.
- Groups analytic accounts by analytic plan (ordered by plan sequence).
- Formats account names with distribution percentages (e.g., `Main Account (50%)` or just `Account Name` if single entry per plan).
- Sorts entries within each plan primarily by plan sequence and secondarily by percentage descending.

### Decimal Precision Configuration
- Adds a dedicated decimal precision setting named `Analytic Percentage` to control the rounding of analytic distribution percentages.

## Technical Details

### Models Created / Extended
- `analytic.distribution.display.mixin`: Abstract model providing `analytic_account_display` (Kostenstelle) (Char, computed, stored).

### Data / Records
- `decimal.precision`: Adds `Analytic Percentage` precision record (`digits = 0` by default).

### Dependencies
- `analytic`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
