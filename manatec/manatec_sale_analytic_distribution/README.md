# manaTec Sale Analytic Distribution Display

This module extends Odoo Sale Order Lines (Verkaufsauftragszeile) with the analytic distribution display feature, integrating human-readable analytic account distribution strings into sale order forms.

## Features

### Sale Order Line (Verkaufsauftragszeile) Extension
- Integrates the `analytic.distribution.display.mixin` into `sale.order.line`.
- Adds the `analytic_account_display` (Kostenstelle) field to order lines in the sale order form view (positioned before the subtotal, optional and hidden by default).

### Automatic Display
- Automatically computes and displays human-readable analytic account names and distribution percentages configured on sale order lines (Verkaufsauftragszeilen).

## Technical Details

### Models Modified
- `sale.order.line`: Inherits `analytic.distribution.display.mixin`.

### Views Modified
- `sale.view_order_form`: Adds `analytic_account_display` (Kostenstelle) field to the order line list view.

### Dependencies
- `sale`
- `manatec_analytic_distribution_display`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
