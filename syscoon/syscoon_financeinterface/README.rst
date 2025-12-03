=========================
syscoon Finance Interface
=========================

Installation
============

To install this module, you need to:

Go to apps and search for syscoon_financeinterface

Description
===========

* Baic module for the finance interface. There will be more modules that extend this module or use this module
  as a dependency.
* syscoon_financeinterface_datev_ascii
* syscoon_partner_accounts
* syscoon_partner_accounts_automatic
* syscoon_partner_accounts_automaitc_invoice
* syscoon_partner_accounts_automaitc_sale
* syscoon_partner_accounts_automaitc_purchase
* syscoon_financeinterface_datev_config_skr03
* syscoon_financeinterface_datev_config_skr04
* syscoon_financeinterface_datev_import
* syscoon_financeinterface_datev_xml
* syscoon_financeinterface_datev_ascii_accounts
* syscoon_financeinterface_enterprise

Changelog
=========

18.0.1.0.6
----------
  * 5011-00095-2: Finance interface menuitem is automatically active without 
  checking the company specific configuration fixed

18.0.1.0.5
----------
  * 5011-00107: adding read access to template for invoice user

18.0.1.0.4
----------
  * 5011-00048-10: Reset invoice after export

18.0.1.0.3
----------
  * CI-00: clean up model syscoon.financeinterface.export

18.0.1.0.2
----------
  * 5011-00048-5: XML Export for suncontacts

18.0.1.0.1
----------
  * 5011-00048-7: Export view corrections

18.0.1.0.0
----------
  * CUS-01710: Fix record singleton for account counterpart

18.0.0.3.7
----------
  * 5011-00197-21: Count of exported records added in the Move/Invoices tab

18.0.0.3.6
----------
  * 5011-00197-3: Type selection restricted for modes

18.0.0.3.5
----------
  * 5011-00197-4: creating export sequence for all companies

18.0.0.3.4
----------
  * CUS-01242: default journal for export

18.0.0.3.3
----------
  * CUS-01297: improve the reset to draft button

18.0.0.3.2
----------
  * CUS-01343: adding all selection mode for datev export for old data to correctly updated by the refactoring

18.0.0.3.1
----------
  * CUS-00962: add force code value to ascii and xml

18.0.0.3.0
----------
  * CUS-01000: add xml regex line to datev template

18.0.0.2.0
----------
  * Refactor from version 16.0.0.2.0

18.0.0.1.1
----------
  * Update method _get_default_accounts to not depend on deprecated fields account_journal_payment_debit_account_id and account_journal_payment_credit_account_id

18.0.0.0.1
----------
  * initial version
  * ported from 17.0.0.1.0

Credits
=======

.. |copy| unicode:: U+000A9 .. COPYRIGHT SIGN
.. |tm| unicode:: U+2122 .. TRADEMARK SIGN

- `Mathias Neef <mathias.neef@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2024

- `Ebin P G <ebin.pg@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2024

- `Omar Abdelaziz <omar.abdelaziz@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2024
