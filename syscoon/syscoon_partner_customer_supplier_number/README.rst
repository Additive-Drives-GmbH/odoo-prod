================================
Customer number/ Supplier number
================================


Installation
============

To install this module, you need to:

#. Go to apps and search for syscoon_partner_customer_supplier_number

Description
===========
* This module adds comprehensive management of customer and supplier numbers for partners in Odoo. It provides:

  - Dedicated fields for customer and supplier numbers in partner records
  - Flexible automatic number generation based on configurable business events
  - Integration with DIN5008 invoice report format to display customer numbers

* Key Features:

Configurable Automatic Number Generation: Choose exactly when customer and supplier numbers should be created:

  - When partners are created
  - When invoices or bills are posted
  - When sale orders are confirmed
  - When purchase orders are confirmed

* Manual Number Creation: Buttons in partner forms for manual number assignment when needed
* User Interface Integration: Numbers appear in partner lists, forms, and can be used in search filters
* Report Integration: Customer numbers can be displayed on invoice reports

Changelog
=========

* 18.0.1.0.0
  * Added new syscoon.numbers.automatic.mode model to define number generation modes
  * Enhanced settings to allow selecting when numbers should be generated automatically
  * Made all trigger points (Partner, Invoice, SO, PO) configurable through checkboxes
  * Updated partner create method to generate numbers based on settings
  * Added invoice posting hook to generate numbers when invoices are posted
  * Modified SO/PO confirmation to check settings before creating numbers
  * Added security access rights for the new model

* 18.0.0.0.1
  * initial version
  * ported from 17.0.0.1.0

Credits
=======

.. |copy| unicode:: U+000A9 .. COPYRIGHT SIGN
.. |tm| unicode:: U+2122 .. TRADEMARK SIGN

- `Omar Abdelaziz <omar.abdelaziz@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025

- `Mathias Neef <mathias.neef@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025

- `Andrés Rojas <andres.rojas@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025
