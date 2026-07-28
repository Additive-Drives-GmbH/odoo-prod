# manaTec Purchase Analytic Distribution Display

This module extends Odoo Purchase Order Lines (Bestellzeile) with the analytic distribution display feature, integrating human-readable analytic account distribution strings into purchase order forms.

## Features

### Purchase Order Line (Bestellzeile) Extension
- Integrates the `analytic.distribution.display.mixin` into `purchase.order.line`.
- Adds the `analytic_account_display` (Kostenstelle) field to order lines in the purchase order form view (positioned before the subtotal, optional and hidden by default).

### Automatic Display
- Automatically computes and displays human-readable analytic account names and distribution percentages configured on purchase order lines (Bestellzeilen).

## Technical Details

### Models Modified
- `purchase.order.line`: Inherits `analytic.distribution.display.mixin`.

### Views Modified
- `purchase.order_form`: Adds `analytic_account_display` (Kostenstelle) field to the order line list view.

### Dependencies
- `purchase`
- `manatec_analytic_distribution_display`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
