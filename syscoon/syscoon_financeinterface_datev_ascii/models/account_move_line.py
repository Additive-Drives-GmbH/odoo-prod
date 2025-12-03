# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.tools import float_is_zero


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _is_datev_invalid_line(self):
        return (
            (
                self.env.company.datev_export_method == "gross"
                and self.tax_repartition_line_id
            )
            or self.account_id.id == self.move_id.export_account_counterpart.id
            or float_is_zero(self.balance, precision_rounding=self.currency_id.rounding)
        )

    def _prepare_datev_errors(self):
        errors = []
        for line in self:
            if line.display_type == "tax":
                continue
            line_name = f"{line.account_id.display_name} with Label ({line.name})"
            if len(line.tax_ids) > 1:
                errors.append(
                    _(
                        "%(line_name)s has more than one tax "
                        "account, but allowed is only one.",
                        line_name=line_name,
                    )
                )
            if line.account_id.datev_automatic_account:
                if not line.account_id.datev_no_tax and not line.tax_ids:
                    errors.append(
                        _(
                            "%(name)s has an automatic account, but there is no tax set.",
                            name=line_name,
                        )
                    )
                else:
                    for tax in line.tax_ids:
                        if tax.id not in line.account_id.datev_automatic_tax.ids:
                            errors.append(
                                _(
                                    "%(line_name)s has an automatic account, but the tax %(tax_name)s is "
                                    "not in the list of the allowed taxes!",
                                    line_name=line_name,
                                    tax_name=tax.name,
                                )
                            )
            if (
                not line.account_id.datev_automatic_account
                and line.tax_ids
                and not line.tax_ids[  # should be related to not invoice lines
                    :1
                ].datev_tax_key
            ):
                errors.append(
                    _(
                        "%(name)s has taxes applied, but the tax has no DATEV Tax Key",
                        name=line_name,
                    )
                )
            if line.account_id.datev_vatid_required and not line.partner_id.vat:
                errors.append(
                    _(
                        "%(name)s needs the VAT-ID, but in the Partner "
                        "%(partner_name)s it is not set",
                        name=line_name,
                        partner_name=line.partner_id.name,
                    )
                )
        return errors

    # ------------------------------------------
    # DATEV Export
    # ------------------------------------------
    def generate_export_line(self, data):  # noqa: C901
        """Generates the amount, the sign, the tax key and the tax case of the move line
        Computes currencies and exchange rates"""
        self.ensure_one()
        data["group"] = True
        interface = data["interface"]
        export = data["lines"][self.id]["export"]

        def _gross(
            compute_type, amount, currency_id, hd_p_include, tax_ids, quantity=False
        ):
            """
            @nested - compute the total include price for the line
            """
            if compute_type == "unit_total":
                taxes_computed = tax_ids.compute_all(
                    amount,
                    quantity=quantity,
                    currency=currency_id,
                    product=self.product_id,
                    partner=self.move_id.partner_id,
                    handle_price_include=hd_p_include,
                )
            else:
                taxes_computed = tax_ids.compute_all(
                    amount, currency_id, handle_price_include=hd_p_include
                )
            return taxes_computed["total_included"]

        is_curr_diff = (
            self.currency_id
            and self.currency_id != self.env.company.currency_id
            and self.amount_currency != 0.0
        )
        total = abs(self.amount_currency) if is_curr_diff else (self.debit or self.credit)
        if self.env.company.datev_export_method == "gross":
            # =========================FIXME: Refactor=================================
            # We need to refactor the code, no need to calculate the price based on taxes
            # we can get the total with existing fields in account.move.line
            # if we do we have to test following scenarios also
            # 1. Check the 'entry' type journal entries are correctly calculating the total
            # 2. Check there are some rounding issues as following export: 48.95 getting as 48.98
            # URL: https://v16-0-dev-datev.odoo-test-staging.7open.eu/web#id=152
            # {TODO: Concat the URL}
            # &cids=3&menu_id=197&action=417&model=syscoon.financeinterface&view_type=form
            # 3. Need to check moves with discount lines
            # 4. Test with journal entries with taxes (move_type == 'entry')
            # =========================================================================
            is_entry = self.move_type == "entry"
            price_unit = (
                total if is_entry else self.price_unit * (1 - self.discount / 100.0)
            )
            quantity = 1 if is_entry else self.quantity
            # Compute the total based on the taxes
            total = _gross(
                compute_type="unit_total",
                amount=price_unit,
                currency_id=self.currency_id,
                hd_p_include=True,
                tax_ids=self.tax_ids,
                quantity=quantity,
            )
            if tax_id := self.tax_ids[:1]:
                if not self.account_id.datev_automatic_account:
                    if tax_id.datev_tax_key:
                        export["BU-Schlüssel"] = tax_id.datev_tax_key
                    if tax_id.datev_tax_case:
                        export["Sachverhalt"] = tax_id.datev_tax_case
                if tax_id.datev_country_id:
                    country_code = tax_id.datev_country_id.code
                    export["EU-Mitgliedstaat u. UStIdNr"] = country_code
                    export["EU-Steuersatz"] = tax_id.amount
            else:
                if (
                    self.account_id.datev_automatic_account
                    and self.account_id.datev_no_tax
                ) or self.move_id.export_account_counterpart.datev_no_tax:
                    export["BU-Schlüssel"] = "40"
        if is_curr_diff:
            base_total = abs(self.balance)
            if self.env.company.datev_export_method == "gross" and self.tax_ids:
                base_total = _gross(
                    compute_type="direct",
                    amount=base_total,
                    currency_id=self.env.company.currency_id,
                    hd_p_include=False,
                    tax_ids=self.tax_ids,
                )
            export["WKZ Umsatz"] = self.currency_id.name
            export["Basis-Umsatz"] = interface.currency_round(
                base_total, self.env.company.currency_id
            )
            export["WKZ Basis-Umsatz"] = self.env.company.currency_id.name
            export["Kurs"] = self.amount_currency / self.balance
        export["Umsatz (ohne Soll/Haben-Kz)"] = interface.currency_round(
            total, self.currency_id
        )
        if self.account_id.datev_vatid_required:
            vat = (
                self.move_id.partner_shipping_id.vat
                or self.move_id.partner_id.vat
                or self.partner_id.vat
            )
            export["EU-Mitgliedstaat u. UStIdNr"] = vat
        export["Auftragsnummer"] = self.move_id.invoice_origin or ""
        export["Festschreibung"] = int(self.env.company.datev_enable_fixing)
        self._apply_kennzeichen(data)
        self._apply_konto(data)
        self._apply_belegdatum(data)
        self._apply_belegfeld_1(data)
        self._apply_belegfeld_2(data)
        self._apply_kost_accounts(data)
        self._apply_buchungstext(data)
        self._apply_beleglink(data)
        self._apply_mandatsreferenz(data)

    def _apply_kennzeichen(self, data):
        export = data["lines"][self.id]["export"]
        export["Soll/Haben-Kennzeichen"] = "S" if self.debit else "H"

    def _apply_belegfeld_1(self, data):
        export = data["lines"][self.id]["export"]
        move = data["lines"][self.id]["datev_move"]
        ref = (
            move.ref
            if data["template"] and data["template"].belegfeld_1_use_ref and move.ref
            else move._get_datev_ref()
        )
        export["Belegfeld 1"] = ref or ""

    def _apply_belegfeld_2(self, data):
        interface = data["interface"]
        export = data["lines"][self.id]["export"]
        payment_term = self.move_id.invoice_payment_term_id
        if payment_term.datev_payment_conditons_id:
            export["Belegfeld 2"] = payment_term.datev_payment_conditons_id
        elif self.move_id.invoice_date_due:
            export["Belegfeld 2"] = interface.convert_date(self.move_id.invoice_date_due)

    def _apply_belegdatum(self, data):
        interface = data["interface"]
        export = data["lines"][self.id]["export"]
        move = self.move_id
        export["Belegdatum"] = interface.convert_date(
            move.date, self.env.company.datev_voucher_date_format
        )
        if move.invoice_date and move.date != move.invoice_date:
            export["Belegdatum"] = interface.convert_date(
                move.invoice_date, self.env.company.datev_voucher_date_format
            )
        if "activate_service_date" in move._fields and move.activate_service_date:
            service_date = (
                move.service_end_date
                if move.service_date_type == "service_period"
                else move.service_delivery_date
            )
            if service_date:
                export["Leistungsdatum"] = interface.convert_date(service_date)
        elif move.delivery_date:
            export["Leistungsdatum"] = interface.convert_date(move.delivery_date)

    def _apply_kost_accounts(self, data):
        if not self.analytic_distribution:
            return
        export = data["lines"][self.id]["export"]
        for analytic_account_id in self._fetch_analytic_accounts():
            if analytic_account_id.plan_id.datev_cost_center == "add_to_kost1":
                export["KOST1 - Kostenstelle"] = analytic_account_id.code
            if analytic_account_id.plan_id.datev_cost_center == "add_to_kost2":
                export["KOST2 - Kostenstelle"] = analytic_account_id.code

    def _apply_konto(self, data):
        interface = data["interface"]
        export = data["lines"][self.id]["export"]
        _rlzero = interface._remove_leading_zero
        account_type = self.account_id.account_type
        counterpart_account = self.move_id.export_account_counterpart
        counterpart_type = counterpart_account.account_type
        lines_with_partner = self._get_lines_with_partner()
        is_one_partner = self.partner_id or len(lines_with_partner) == 1
        line_partner = self.partner_id.commercial_partner_id
        partner = lines_with_partner[:1].partner_id.commercial_partner_id
        creditor_number = line_partner.creditor_number or partner.creditor_number
        debitor_number = line_partner.debitor_number or partner.debitor_number
        if is_one_partner:
            if account_type == "liability_payable" and line_partner.creditor_number:
                export["Konto"] = _rlzero(line_partner.creditor_number)
            if account_type == "asset_receivable" and line_partner.debitor_number:
                export["Konto"] = _rlzero(line_partner.debitor_number)
            if counterpart_type == "liability_payable" and creditor_number:
                export["Gegenkonto (ohne BU-Schlüssel)"] = _rlzero(creditor_number)
            if counterpart_type == "asset_receivable" and debitor_number:
                export["Gegenkonto (ohne BU-Schlüssel)"] = _rlzero(debitor_number)
        if not export["Konto"]:
            export["Konto"] = _rlzero(self.account_id.code)
        if not export["Gegenkonto (ohne BU-Schlüssel)"]:
            export["Gegenkonto (ohne BU-Schlüssel)"] = _rlzero(counterpart_account.code)

    def _apply_buchungstext(self, data):
        export = data["lines"][self.id]["export"]
        bookingtext_obj = self.env["syscoon.financeinterface.bookingtext.config"].sudo()
        labels = bookingtext_obj.search(
            [("journal_id", "=", self.journal_id.id)], order="sequence asc"
        )
        if not labels:
            labels = bookingtext_obj.search([], order="sequence asc")
        bookingtext = []
        for label in labels:
            if value := self.get_field(label.field):
                bookingtext.append(value)
        bookingtext = ", ".join(bookingtext) if bookingtext else self.name
        export["Buchungstext"] = (bookingtext or self.move_id.name)[:60]

    def _apply_beleglink(self, data):
        if self.company_id.datev_use_bedi and self.move_id.datev_bedi:
            export = data["lines"][self.id]["export"]
            export["Beleglink"] = 'BEDI "%s"' % self.move_id.datev_bedi or ""

    def _apply_mandatsreferenz(self, data):
        if "sdd_mandate_id" in self.move_id._fields:
            export = data["lines"][self.id]["export"]
            export["SEPA-Mandatsreferenz"] = self.move_id.sdd_mandate_id.name or ""

    # -------------helpers-------------------
    def _get_lines_with_partner(self):
        return self.move_id.line_ids.filtered(
            lambda l: l.partner_id and l.partner_id != self.partner_id
        )

    def get_field(self, field_name):
        for part in field_name.split("."):
            if part in ["move_id", "partner_id"]:
                self = getattr(self, part)
            else:
                value = getattr(self, part)
        return value
