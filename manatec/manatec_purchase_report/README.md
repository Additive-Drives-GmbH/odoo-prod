# manaTec Purchase Report

Dieses Modul erweitert die Einkaufsdokumente um zusätzliche Informationen.

## Features
- Im Infoblock der Einkaufsdokumente (DIN 5008) werden die Felder "USt-IdNr." (`vat`) und "Referenz Nr" (`origin`) am Ende des Informationsblocks hinzugefügt.
- Die Bezeichnung des Feldes wurde von "Source Document" in "Reference Nr" geändert und für Deutsch als "Referenz Nr:" übersetzt.
- Arbeitet mit XPaths zur sauberen Erweiterung des bestehenden Templates `l10n_din5008_purchase.report_common_purchase_din5008_template_document_information`.
