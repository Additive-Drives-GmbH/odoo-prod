# manaTec Sale Pre/Post Text

This module extends Odoo Sale Orders (Verkaufsauftrag) with a Pre-Text tab printed before the product table on the quotation/order PDF report and the online quotation preview, and moves the Terms and Conditions (AGB) field into its own Post-Text tab.

## Features

### Sale Order (Verkaufsauftrag) Extension
- Adds a `pre_text` HTML field to `sale.order`.
- Adds a "Pre-Text" notebook page directly after the "Order Lines" page, containing the `pre_text` field.
- Adds a "Post-Text" notebook page directly after "Pre-Text", containing the existing `note` (Terms and Conditions / AGB) field, moved out of the "Order Lines" page.

### Report & Online Preview
- Prints the `pre_text` field on the quotation/order PDF report, directly before the product data table.
- Shows the `pre_text` field in the online quotation preview (customer portal), directly before the product data table, the same way the Terms & Conditions and Payment Terms sections are shown there.

## Technical Details

### Models Modified
- `sale.order`: Adds the `pre_text` (Html) field.

### Views Modified
- `sale.view_order_form`: Adds "Pre-Text" and "Post-Text" pages after "Order Lines"; relocates the `note` field into "Post-Text".

### Reports Modified
- `sale.report_saleorder_document`: Prints `pre_text` before the product table.
- `sale.sale_order_portal_content`: Shows `pre_text` before the product table in the online quotation preview.

### Dependencies
- `sale`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
