# manaTec CRM Buyer

This module extends Odoo CRM Leads/Opportunities with a Buyer field, linking the customer-side purchasing contact (res.partner) and storing their email for quick reference.

## Features

### Lead/Opportunity (crm.lead) Extension
- Adds a `buyer_id` (Many2one to `res.partner`) field to `crm.lead`, linking the purchasing contact on the customer side.
- Adds a `buyer_email` (Char, computed and stored, read-only) field to `crm.lead`, holding the buyer's email for quick reference.
- `buyer_email` is computed from `buyer_id.email` and cannot be edited manually.
- Shows both fields in opportunities in the "Contacts" tab, under "Contact Information", alongside the existing contact fields (`contact_name`, `function`, `website`).
- Show both fields in leads below the Mail/Phone fields

## Technical Details

### Models Modified
- `crm.lead`: Adds the `buyer_id` (Many2one) field and the `buyer_email` (Char, computed and stored from `buyer_id.email`, read-only) field.

### Views Modified
- `crm.crm_lead_view_form`: Adds the Buyer and Buyer Email fields inside the "Contact Information" group of the "Contacts" tab.

### Dependencies
- `crm`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
