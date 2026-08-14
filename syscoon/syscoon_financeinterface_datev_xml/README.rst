====================================
syscoon Finance Interface Enterprise
====================================

Installation
============

To install this module, you need to:

#. Go to apps and search for syscoon_financeinterface_datev_xml

Description
===========

* Module that allows to export documents to DATEV Unternehmen Online

Changelog
=========

19.0.0.2.14
-----------
  * 5000-00056:
    * Fix X-Rechnungen export skipping bills whose e-invoice XML is linked to the ubl_cii_xml_file binary field (e.g. bills migrated from earlier versions), which is hidden from move.attachment_ids by the implicit res_field filter
    * Detect XML attachments stored with mimetype text/plain (XML uploaded by users without Settings access) via the file extension

19.0.0.2.13
-----------
  * DV19-00056: Restrict X-Rechnungen export to Vendor Bills only - the "Invoices" field is locked to Vendor Bills and customer invoices are excluded from the move selection

19.0.0.2.12
-----------
  * DV19-00056: X-Rechnungen export now only includes XML files, excluding Odoo-generated PDFs from the ZIP and document.xml manifest
  * DV19-00056: Fix XML attachment detection to support both application/xml and text/xml mimetypes for imported XRechnung files

19.0.0.2.11
-----------
  * CUS-02368: Changing city cutoff in XML and ASCII

19.0.0.2.10
-----------
  * CUS-02333: Export <payment_conditions> with due_date and payment_conditions_text when an invoice has only a due date and no payment term

19.0.0.2.9
----------
  * CUS-02074: Preserve embedded factur-x.xml in PDF exports by skipping merge for single PDFs

19.0.0.2.8
----------
  * CUS-02098: add 'Retry Failed Items' button and fix log not clearing after successful retry

19.0.0.2.7
----------
  * migration to Odoo 19.0
  * ported from 18.0.0.2.8

18.0.0.2.8
----------
  * FML-00019: Removed creating invoice XML when only exporting BEDI

18.0.0.2.7
----------
  * CUS-02012: Add option to decrypt PDF files that are encrypted

18.0.0.2.6
----------
  * CUS-01914: Fix issues with bedi financeinterface exports

18.0.0.2.5
----------
  * 5011-00118: fixing pdf attachment search to include res_field attachments

18.0.0.2.4
----------
  * 3d-00032-1: Made mandatory fields check for partner as system parameter configuration

18.0.0.2.3
----------
  * CI-00: code cleanup

18.0.0.2.2
----------
  * CUS-01905: fixing xml and pdf mismatch when exporting 

18.0.0.2.0
----------
  * 5011-00095-1: XML Export -Handle X-Rechnung to export only Vendor Bills and only if attachment is xml-format

18.0.0.2.1
----------
  * 5011-00048-4: XML Export -Handle X-Rechnung export exclusively with XML only

18.0.0.1.10
-----------
  * CUS-01835: adding check for corrupted pdfs during export


18.0.0.1.9
----------
  * 5011-00048-5: XML Export - Sub-contacts

18.0.0.1.8
----------
  * 5011-00048-7: Export view corrections

18.0.0.1.7
----------
  * CUS-01407: export_xml_mode selection corrections in company settings

18.0.0.1.6
----------
  * 5011-00197-8: Mandatory partner fields check before export

18.0.0.1.5
----------
  * 5011-00064-2: better xml export for datev

18.0.0.1.3
----------
  * 5011-00197-8: Add log errors for street, vat and customer_number mandatory
  * 5011-00197-8: Make street, vat and customer_number mandatory

18.0.0.1.2
----------
  * 5011-00197-3: Type selection restricted for modes

18.0.0.1.1
----------
  * 5011-00197-8: fix wrong field added

18.0.0.1.0
----------
  * refactor from 17.0.0.3.3

18.0.0.0.2
----------
  * Refactor from version 16.0.0.1.0

18.0.0.0.1
----------
  * migrated from 17.0.0.1.0

Credits
=======

.. |copy| unicode:: U+000A9 .. COPYRIGHT SIGN
.. |tm| unicode:: U+2122 .. TRADEMARK SIGN

- `Mathias Neef <mathias.neef@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025

- `Ebin P G <ebin.pg@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025

- `Omar Abdelaziz <omar.abdelaziz@syscoon.com>`__ |copy|
  `syscoon <http://www.syscoon.com>`__ |tm| 2025
