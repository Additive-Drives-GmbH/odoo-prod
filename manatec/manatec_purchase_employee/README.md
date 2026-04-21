# manaTec Purchase Employee

This module extends the Odoo Purchase and HR modules to provide better employee tracking and shorthand identification on purchase orders.

## Features

### HR Employee Extensions
- Added a "Shorthand" field to the employee model.
- The "Shorthand" field is also available on the public employee profile.

### Purchase Order Extensions
- Added an "Employee" field to Purchase Orders, allowing you to link a specific employee to the order.
- This field is located below the "Source Document" (origin) field in the purchase order form view.
- Added a "Shorthand" field to Purchase Orders that automatically retrieves the "Shorthand" from the selected employee.
- Added a search field and a quick filter for "Shorthand" in both Purchase Order and Request for Quotation search views.

### Automatic Synchronization
- When an employee is selected on a purchase order, the shorthand field is automatically populated.
- The shorthand field is stored and searchable
- Updates to an employee's shorthand will automatically propagate to linked purchase orders.

## Technical Details

### Models Modified
- `hr.employee`: Added `shorthand` (Char)
- `hr.employee.public`: Added `shorthand` (Char, related)
- `purchase.order`: Added `employee_id` (Many2one to `hr.employee`) and `shorthand` (Char, computed, stored)

### Dependencies
- `base`
- `purchase`
- `hr`

## Author
- manaTec GmbH
- Website: https://www.manatec.de
- Support: info@manatec.de
