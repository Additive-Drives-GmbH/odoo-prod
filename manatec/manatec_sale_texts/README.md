# manaTec Sale Texts

This module extends Odoo Sale Orders (Verkaufsauftrag) with a dedicated Pre-Text field and reorganizes the existing Terms and conditions (AGB) field into separate notebook tabs.

## Features

### Sale Order (Verkaufsauftrag) Extension
- Adds a `pre_text` (Pre-Text) HTML field to `sale.order`.
- Adds a "Pre-Text" tab directly after the "Order Lines" tab, containing the new `pre_text` field.
- Adds a "Post-Text" tab directly after the "Pre-Text" tab, containing the relocated `note` (Terms and conditions / AGB) field.

### Quotation Report
- Prints the Pre-Text content before the product lines table on the quotation/sale order report, when set.

### Customer Portal
- Displays the Pre-Text content, formatted like the existing "Terms & Conditions" and "Payment terms" sections, before the order lines table on the customer portal quotation page, when set.

## Technical Details

### Models Modified
- `sale.order`: Adds the `pre_text` Html field.

### Views Modified
- `sale.view_order_form`: Adds "Pre-Text" and "Post-Text" tabs after "Order Lines"; moves the `note` field into the "Post-Text" tab.
- `sale.report_saleorder_document`: Prints `pre_text` before the product lines table.
- `sale.sale_order_portal_content`: Displays `pre_text` before the order lines table.

### Dependencies
- `sale`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
