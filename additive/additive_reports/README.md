================
Additive Reports
================

Additive Reports

This Module Handle customizations in reports for additive

**Table of contents**

.. contents::
   :local:

Changelog
=========

- 18.0.1.0.0: initial version
- 18.0.1.0.1: Adjust logo bottom space and company address line width remove delivery address from right side
- 18.0.1.0.2: refactoring footer and moving company.report_header from header into footer
- 18.0.1.0.3: Consistent font size
- 18.0.1.0.4: DIN 5008 improvements
- 18.0.1.0.5: Removed date_done logic and re-enabled delivery_date field
- 18.0.1.0.7: DIN 5008 invoice report improvements:
    - Hide the totals table when using the company currency (moved the ``d-none`` logic into a dedicated template).
    - Reorganized invoice report XPath logic for better readability and maintainability.
    - Standardized label text by removing unnecessary punctuation.
    - Adjusted SCSS styles: address element width and font sizing in DIN 5008 reports.
- 18.0.1.0.8: Added general border width to reports
- 18.0.1.0.9: DIN 5008 invoice report improvements:
    - Limit the information block width to 100mm instead of letting it grow unbounded (which scaled down the whole page).
    - Wrap only the Purchase Order No. value, and only at spaces.
    - Let the e-mail value overflow the information block instead of wrapping.
    - Show the ``our_nr_by_customer`` field only on customer documents (out_invoice/out_refund).
    - Use a document-type specific report title (Invoice / Credit Note / Cancelled Invoice / Vendor Bill / Vendor Credit Note) with German translations (Stornorechnung, Gutschrift, ...).
- 19.0.1.0: Migration to Odoo 19.0
    - remove most of the customizations


Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/Additive-Drives-GmbH/odoo-prod/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/Additive-Drives-GmbH/odoo-prod/issues/new?body=module:%20additive_reports%0Aversion:%2018.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
-------

* IFE Gesellschaft für Forschung und Entwicklung
* manaTec GmbH

Contributors
------------

- Akram Tarabichi https://www.ife.de
- Fouzia Benjarrari https://www.ife.de
- Lars Halbauer https://www.manatec.de

Maintainers
-----------

This module is part of the `https://github.com/Additive-Drives-GmbH/odoo-prod`_ project on GitHub.

You are welcome to contribute.
