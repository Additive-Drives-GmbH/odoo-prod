# Odoo Pipedrive Integration — User Guide (Odoo 19)

**Bi-directional connector** between Odoo and Pipedrive. Sync Companies, Contacts, Leads, Opportunities, Products, Users, and related Activities between both systems.

---

## Table of Contents

1. [What This Connector Does](#what-this-connector-does)
2. [Before You Start](#before-you-start)
3. [Connect Your Pipedrive Account](#connect-your-pipedrive-account)
4. [First-Time Setup Checklist](#first-time-setup-checklist)
5. [Setup Fields (Required Pipedrive Fields)](#setup-fields-required-pipedrive-fields)
6. [Configure Each Entity Tab](#configure-each-entity-tab)
7. [Dropdown Mapping Guides](#dropdown-mapping-guides)
8. [Running Sync](#running-sync)
9. [Automatic Schedulers](#automatic-schedulers)
10. [Manual Sync by Record ID](#manual-sync-by-record-id)
11. [Syncing Individual Records from Odoo](#syncing-individual-records-from-odoo)
12. [Activities & Related Records](#activities--related-records)
13. [Logs & Monitoring](#logs--monitoring)
14. [Maintenance Options](#maintenance-options)
15. [Common Setup Scenarios](#common-setup-scenarios)
16. [Quick Reference](#quick-reference)

---

## What This Connector Does

| Odoo | Pipedrive |
|------|-----------|
| Companies (Organizations) | Organizations |
| Contacts (Persons) | Persons |
| Leads | Leads |
| Opportunities (Deals) | Deals |
| Products | Products |
| Users | Users |
| Activities (Notes, Calls, Tasks, Meetings, Emails) | Activities |

**Sync directions supported:**
- **Odoo → Pipedrive** — push records from Odoo to Pipedrive
- **Pipedrive → Odoo** — pull records from Pipedrive into Odoo

You control sync per entity using toggles and buttons on the **Pipedrive Instance** form.

---

## Before You Start

### In Pipedrive
- You need an **API token** (Pipedrive → Settings → Personal preferences → API).
- Your Pipedrive account should have Companies, Contacts, Deals, Leads, and Products set up as you plan to use them.

### In Odoo
- Install the **Odoo Pipedrive Integration** app.
- Open the main menu: **Odoo Pipedrive Integration**.
- Only one Pipedrive instance can be **Active (Connected)** at a time.

### Recommended Odoo master data (before first sync)
| For syncing… | Prepare in Odoo |
|--------------|-----------------|
| Opportunities | CRM Stages + Sales Teams |
| Leads | UTM Sources (for channel mapping) |
| Products | Product Categories (for category mapping) |
| All entities | Users linked where owner mapping is needed |

---

## Connect Your Pipedrive Account

1. Go to **Odoo Pipedrive Integration → Pipedrive Instance**.
2. Open your instance (or create one).
3. Fill in:
   - **Pipedrive App Token** — your API token
   - **Pagination Size** — how many records to fetch per batch (1–200; default 25)
   - **Base URL** — your company API URL, e.g. `https://yourcompany.pipedrive.com/api/v2`
4. Click **Active** to mark the instance as connected.
5. Click **Test API Connection**.
   - If the token is valid but Base URL is empty, you will see a warning — add the Base URL before running full sync.
6. Save the form.

> **Tip:** Keep the instance **Active** only when you want sync to run. Use **Inactive** to pause all integration activity.

---

## First-Time Setup Checklist

Complete these steps once for a new installation:

| Step | Action | Where |
|------|--------|-------|
| 1 | Connect & test API | Top buttons on Pipedrive Instance |
| 2 | **Setup Fields** | Top button — creates required Pipedrive custom fields |
| 3 | **Import Fields** on each entity tab | Companies, Contacts, Leads, Opportunities, Products |
| 4 | **Refresh Stage & Pipeline Mapping** | Opportunities tab |
| 5 | **Refresh Channel Mapping** | Leads tab |
| 6 | Set product category mapping manually | Products tab (if you use categories) |
| 7 | Review **Field Mapping** table on each tab | Adjust if needed |
| 8 | Run a manual sync test | Sync buttons on each tab |
| 9 | Enable schedulers (optional) | Activate Scheduler toggles + **Schedulers** button |

---

## Setup Fields (Required Pipedrive Fields)

The connector needs two custom fields in Pipedrive for each entity:

| Field | Purpose |
|-------|---------|
| **sync_to_odoo** | Yes/No — controls whether a Pipedrive record should sync to Odoo |
| **odoo_id** | Stores the linked Odoo record ID |

### How to create them

**Option A — All entities at once (recommended first time):**
1. Click **Setup Fields** in the top button bar.
2. The connector creates missing fields automatically for Companies, Contacts, Opportunities, and Products.

**Option B — One entity at a time:**
- Use **Create Required Pipedrive Fields** at the bottom of each entity tab (Companies, Contacts, Leads, Opportunities, Products).

### About Leads
Leads in Pipedrive **use the same custom fields as Opportunities (Deals)**. If you sync leads, ensure those fields exist on deals in Pipedrive. The connector will guide you if manual setup is needed for lead-specific fields.

After Setup Fields, click **Import Fields** on each tab to refresh the field list in Odoo.

---

## Configure Each Entity Tab

Each tab on the Pipedrive Instance form follows the same layout:

### Left side — Odoo to Pipedrive
- **Activate Scheduler** — enable automatic push from Odoo to Pipedrive
- **Last Sync Datetime** — when Odoo records were last pushed
- **Dropdown Mapping** — value mappings for dropdown/selection fields
- **SYNC ODOO TO PIPEDRIVE** — run a manual push now

### Right side — Pipedrive to Odoo
- **Activate Scheduler** — enable automatic pull from Pipedrive to Odoo
- **Last Sync Datetime** — when Pipedrive records were last pulled
- **Dropdown Mapping** — value mappings for dropdown/selection fields
- **SYNC PIPEDRIVE TO ODOO** — run a manual pull now

### Field Mapping table
Maps which Odoo field corresponds to which Pipedrive field. Default mappings are created when you click **Import Fields**. You can adjust rows in the table if your setup requires different mappings.

### Import Fields button
Loads the latest field definitions from both Odoo and Pipedrive and rebuilds default field mappings. Run this after:
- Setup Fields
- Adding new custom fields in Pipedrive
- Changing field structure in either system

---

## Dropdown Mapping Guides

Some fields use dropdown values (stages, channels, yes/no flags). The connector handles these differently per entity:

### Companies & Contacts
- Dropdown mapping is **auto-generated** when you import fields.
- Fields are **read-only** — do not edit manually.

### Opportunities (Deals) — Stages & Pipelines
- Mapping is **auto-generated** from your live Pipedrive pipelines and stages.
- Fields are **read-only**.

**How stages are matched:**
1. By **exact name** (Pipedrive stage name = Odoo CRM stage name)
2. If names differ, by **order** (Pipedrive stage order vs Odoo stage sequence)

**How pipelines are matched:**
- Each Pipedrive **pipeline name** must match an Odoo **Sales Team** name (case-insensitive).
- If you have **one pipeline** in Pipedrive and **one sales team** in Odoo, they link automatically.

**When to refresh:** After adding or renaming stages, pipelines, or sales teams — click **Refresh Stage & Pipeline Mapping**.

**Prepare in Odoo:** CRM → Configuration → Stages and Sales Teams.

### Leads — Channel / UTM Source
- Mapping is **auto-generated** from Pipedrive channel options.
- Fields are **read-only**.

**How channels are matched:**
1. By **exact name** (Pipedrive channel = Odoo UTM Source name)
2. If names differ, by **list order**

**When to refresh:** After adding or renaming channels or UTM sources — click **Refresh Channel Mapping**.

**Prepare in Odoo:** CRM → Configuration → UTM Sources.

### Products — Category
- Category mapping is **manual** — edit the Dropdown Mapping fields directly on the Products tab.
- Map Pipedrive product category values to Odoo Product Category IDs as needed.

---

## Running Sync

### Manual sync (on demand)
On any entity tab, use:
- **SYNC ODOO TO PIPEDRIVE** — push Odoo records to Pipedrive
- **SYNC PIPEDRIVE TO ODOO** — pull Pipedrive records into Odoo

### Which records sync?

**From Odoo to Pipedrive:**
- Records must have **Sync to Pipedrive = Yes** on the record form (Contacts, Leads, Opportunities, Products).
- Records must be **Active**.

**From Pipedrive to Odoo:**
- Records must have **sync_to_odoo = Yes** in Pipedrive (the custom field created by Setup Fields).

### First sync date
- On the first sync, if no last sync date is set, the connector uses the current time as a starting point.
- The date is saved after sync completes successfully.

---

## Automatic Schedulers

### Enable per entity
Turn on **Activate Scheduler** on the left or right side of each entity tab for the direction you want automated.

### View schedulers
Click **Schedulers** in the top button bar to open all scheduled jobs linked to the integration.

Default scheduled jobs include:
- **Fetch Odoo and Pipedrive All Modules Data** — runs entity sync on a schedule (every 30 minutes when enabled)
- **Fetch Pipedrive Activities** — syncs activities (every 30 minutes when enabled)

> Schedulers only process entities where the **Activate Scheduler** toggle is ON for that direction.

---

## Manual Sync by Record ID

Use these menus under **Odoo Pipedrive Integration** to sync specific Pipedrive records by ID:

| Menu | Use for |
|------|---------|
| **Pipedrive To Odoo** | Pull specific Pipedrive records into Odoo |
| **Partner Pipedrive To Odoo** | Contacts / Companies by Pipedrive ID |
| **CRM Pipedrive To Odoo** | Leads / Opportunities by Pipedrive ID |
| **Product Pipedrive To Odoo** | Products by Pipedrive ID |
| **User Pipedrive To Odoo** | Users by Pipedrive ID |

**Format for multiple IDs:** `123,456,789`  
**Format for single ID:** `123`

---

## Syncing Individual Records from Odoo

On individual record forms, a **Pipedrive Integration** tab and sync button are available:

| Odoo record | Sync button / field |
|-------------|---------------------|
| Contact / Company | **Sync to Pipedrive** field + **SYNC TO PIPEDRIVE** button |
| Lead / Opportunity | **Sync to Pipedrive** field + sync actions |
| Product | **Sync to Pipedrive** field + sync actions |
| User | User sync options |

Set **Sync to Pipedrive = Yes** on records you want included in Odoo → Pipedrive sync.

---

## Activities & Related Records

### Per-entity activity toggles
On Companies, Contacts, Leads, and Opportunities tabs, enable which activity types to sync:
- Notes
- Emails
- Tasks
- Meetings
- Calls
- Files (Opportunities only)

### Sync Association tab
- **SYNC RELATED ACTIVITIES** — pull activities from Pipedrive to Odoo
- **Import Activity Fields** — load activity field definitions
- Enable **Activate Scheduler** for automatic activity sync

### Related modules (Pipedrive → Odoo)
When syncing from Pipedrive, you can optionally include linked records:
- Contacts linked to a Lead, Deal, or Company
- Companies linked to a Lead or Deal

Turn these on using the **Sync Related Modules** toggles on each entity tab.

---

## Logs & Monitoring

### Pipedrive Logs
Go to **Odoo Pipedrive Integration → Pipedrive Logs** to review:
- Successful syncs
- Warnings (e.g. unmapped dropdown values)
- Errors (connection issues, missing fields)

Check logs whenever sync results look wrong or records are skipped.

### Chatter on Pipedrive Instance
The instance form has a chatter panel showing recent integration activity and messages.

---

## Maintenance Options

On the **Delete Logger** tab:

| Option | Purpose |
|--------|---------|
| **Remove Logger Records Scheduler** | Automatically delete old log entries |
| **Remove Last Month Log** | How many months of logs to keep |
| **Delete Filters** | Clean up Pipedrive filter records stored in Odoo |
| **Import Lead Labels** | Pull lead labels from Pipedrive into Odoo |
| **Export Lead Labels** | Push Odoo lead labels to Pipedrive |

---

## Common Setup Scenarios

### Scenario 1 — New installation, sync everything
1. Connect instance → Test API Connection
2. Setup Fields
3. Import Fields on all tabs
4. Refresh Stage & Pipeline Mapping (Opportunities)
5. Refresh Channel Mapping (Leads)
6. Set product category mapping if needed (Products)
7. Run manual sync on each tab to test
8. Enable schedulers

### Scenario 2 — Added a new Pipedrive stage
1. Open Opportunities tab
2. Click **Refresh Stage & Pipeline Mapping**
3. Verify mapping in the read-only Dropdown Mapping fields
4. Run **SYNC PIPEDRIVE TO ODOO** or wait for scheduler

### Scenario 3 — Added a new marketing channel in Pipedrive
1. Create matching UTM Source in Odoo (same name)
2. Open Leads tab
3. Click **Refresh Channel Mapping**
4. Run sync

### Scenario 4 — Pipeline not mapping (empty pipeline mapping)
1. In Odoo: CRM → Configuration → Sales Teams — note team names
2. In Pipedrive: rename pipelines to match team names exactly
3. Click **Refresh Stage & Pipeline Mapping**
4. Check logs if still empty

### Scenario 5 — Only sync selected Odoo records
1. On each record, set **Sync to Pipedrive = Yes**
2. Run **SYNC ODOO TO PIPEDRIVE** manually or enable scheduler
3. Only records marked Yes will be pushed

---

## Quick Reference

### Top buttons (Pipedrive Instance form)

| Button | Action |
|--------|--------|
| **Active / Inactive** | Enable or pause the integration |
| **Test API Connection** | Verify API token and connection |
| **Setup Fields** | Create required Pipedrive custom fields |
| **Schedulers** | View and manage scheduled sync jobs |

### Per-tab buttons

| Button | Action |
|--------|--------|
| **Create Required Pipedrive Fields** | Setup fields for that entity only |
| **Import Fields** | Load field definitions and rebuild mappings |
| **Refresh Stage & Pipeline Mapping** | Rebuild deal stage/pipeline maps (Opportunities only) |
| **Refresh Channel Mapping** | Rebuild lead channel maps (Leads only) |
| **SYNC ODOO TO PIPEDRIVE** | Manual push |
| **SYNC PIPEDRIVE TO ODOO** | Manual pull |

### Entity tabs

| Tab | Syncs |
|-----|-------|
| Users | Odoo Users ↔ Pipedrive Users |
| Companies | Odoo Companies ↔ Pipedrive Organizations |
| Contacts | Odoo Contacts ↔ Pipedrive Persons |
| Leads | Odoo Leads ↔ Pipedrive Leads |
| Opportunities | Odoo Opportunities ↔ Pipedrive Deals |
| Products | Odoo Products ↔ Pipedrive Products |
| Sync Association | Activities |
| Delete Logger | Log cleanup, filters, lead labels |

---

**Support:** [echoBitz IT Solutions](https://www.echobitzit.com/contactus)

**Version:** Odoo 19 — Odoo Pipedrive Integration
