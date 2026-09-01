# manaTec Contact NDA

This module extends Odoo Contacts with an NDA Valid Until date field and a scheduled action that creates a reminder activity a configurable number of months before expiry.

## Features

### Contact (res.partner) Extension
- Adds an `nda_valid_until` (Date) field to `res.partner`, shown in the "Sales & Purchase" tab.

### Scheduled Action
- Adds a "Contact: Check NDA Expiry" scheduled action (daily, inactive by default) that scans contacts with `nda_valid_until` set.
- The entire reminder logic lives in the scheduled action's `code` field, not in the module's Python code — this is intentional, since the thresholds/logic aren't considered fixed business rules and an admin should be able to tweak them (or the whole flow) without a module change/upgrade. Editable directly in Settings → Technical → Scheduled Actions. The shipped default code declares:
  - `NDA_MONTHS_BEFORE` — how many months before the expiry date the reminder should fire.
  - `NDA_ACTIVITY_TYPE_XMLID` — external ID of the activity type to create (defaults to `mail.mail_activity_data_todo`, "To Do").
  - `NDA_DEFAULT_USER_ID` — database ID of the fallback responsible user (defaults to `2`; an admin should double check/adjust this per database before activating the cron).
- Responsible user logic: if exactly one of the contact's `user_id` (Salesperson) / `buyer_id` (Buyer, from `purchase`) is set, that person is assigned the activity; if neither or both are set, the configured default user is used instead. If no responsible user can be determined at all, the contact is skipped.
- A contact that already has a pending activity of the configured type is skipped, so the reminder is only created once per expiry.
- The activity summary includes the expiry date formatted according to the responsible user's language (falling back to the scheduler's language), via `res.lang.date_format`.

## Technical Details

### Models Modified
- `res.partner`: Adds `nda_valid_until` (Date) only. No other model changes — the reminder logic below lives purely in cron data, not in Python.

### Views Modified
- `base.view_partner_form`: Adds the NDA field to the "Sales & Purchase" tab.

### Data
- `ir_cron_check_nda_expiry`: the scheduled action, including its full reminder logic in `code`, `noupdate="1"` so admin edits survive module upgrades.

### Dependencies
- `purchase` (for the `buyer_id` field on `res.partner`)
- `mail` (for `mail.activity.mixin` / `activity_schedule` on `res.partner`)

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
