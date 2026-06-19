.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
:target: https://www.gnu.org/licenses/agpl
:alt: License: AGPL-3

============================================
syscoon Finanzinterface - DATEV ASCII Export
============================================

Installation
============

To install this module, you need to:

Go to apps and search for syscoon Finanzinterface - DATEV ASCII Export

Usage
=====
*

Change Log
==========

18.0.1.1.13
-----------
  * 5011-00194: fix tax rounding correction skipped under round_globally due to float comparison; compare drift against safety threshold using currency precision

18.0.1.1.12
-----------
  * DV19-00052: fix Leistungsdatum date format to DDMMYYYY (8-digit, 4-digit year) per DATEV specification

18.0.1.1.11
-----------
  * DV19-00051: Add "Enable Reverse Credit/Debit" setting for DATEV ASCII export

18.0.1.1.10
-----------
  * CUS-02207: fix tax rounding correction for journal entries and apply correction after rounding

18.0.1.1.9
-----------
  * CUS-02098: fix rounding issue in gross export by using compute_all with unrounded sum

18.0.1.1.8
-----------
  * CUS-02056: Fix tax rounding difference in vendor bill exports

18.0.1.1.7
-----------
  * CUS-01914: Fix issues with the DATEV ASCII export csv total

18.0.1.1.6
-----------
  * CUS-01914: FIX issue with the csv total (tax rounding issue)

18.0.1.1.5
----------
  * 5011-00120: Fix error when batch payment is used

18.0.1.1.4
----------
  * CI-00: Fix access to finance interface template when feature is not activated

18.0.1.1.3
----------
  * CI-00: Fix access to finance interface template when feature is not activated

18.0.1.1.3
----------
  * 5011-00064-6: fix migration script with False value
  

18.0.1.1.2
----------
  * 5011-00064-6: Add Missing DATEV Ref. to Bills or Invoices
  
18.0.1.1.1
----------
  * 5011-00048-9: Belegfeld 1 field should be set with name in ASCII EXPORT if ref is not set
  
18.0.1.1.0
----------
  * CUS-01645: DATEV ASCII - Field "datev_ref" fix store strange behavior

18.0.0.1.5
----------
  * 5011-00085: Correction in datev_ref field

18.0.0.1.4
----------
  * 5011-00197-22: DATEV ASCII - Field "Delivery date" added to the export

18.0.0.1.3
----------
  * 5011-00197-12: fixing error with customer invoice ascii export

18.0.0.1.2
----------
  * 5011-00197-3: Type selection restricted for modes
  * 5011-00197-5: adding condition for bedi link

18.0.0.1.1
----------
  * CUS-01242: default journal for export

18.0.0.1.0
----------
  * Refactor from version 17.0.0.2.0

18.0.0.0.1
----------
  * Refactor from version 16.0.0.1.6


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
