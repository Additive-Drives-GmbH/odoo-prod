# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo import _, fields, models
from odoo.tools import float_repr

from .utilities import _etree_subelement, _float_to_string

EU_VAT = [
    "BE",
    "BG",
    "DK",
    "DE",
    "EE",
    "FI",
    "FR",
    "EL",
    "GB",
    "IE",
    "IT",
    "HR",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "AT",
    "PL",
    "PT",
    "RO",
    "SE",
    "SK",
    "SI",
    "ES",
    "CZ",
    "HU",
    "CY",
]


class AccountMove(models.Model):
    """Adds the posibility to check the move line if they are compatible for
    the DATEV export"""

    _inherit = "account.move"

    datev_bedi_export_id = fields.Many2one(
        "syscoon.financeinterface", "BEDI Export", copy=False
    )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # ++++++++++++++++++++++ DATEV XML Processing ++++++++++++++++
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _process_datev_xml_all(self, data):
        self._process_datev_xml_invoice_info(data)
        self._process_datev_xml_accounting_info(data)
        self._process_datev_xml_invoice_party(data)
        self._process_datev_xml_supplier_party(data)
        self._process_datev_xml_payment_conditions(data)
        self._process_datev_xml_invoice_item_list(data)
        self._process_datev_xml_total_amount(data)
        self._process_datev_xml_additional_info_footer(data)

    def _process_datev_xml_invoice_info(self, data):
        invoice_info = etree.SubElement(data["element"], "invoice_info")
        for key, val in self._prepare_datev_xml_invoice_info(data).items():
            invoice_info.attrib[key] = data["key_apply"](
                data["template_keys"], key, _float_to_string(val)
            )
        if order_value := data["key_apply"](data["template_keys"], "order_id", ""):
            invoice_info.attrib["order_id"] = order_value

    def _process_datev_xml_accounting_info(self, data):
        if data["mode"] == "extended":
            account_info = etree.SubElement(data["element"], "accounting_info")
            for key, val in self._prepare_datev_xml_accounting_info(data).items():
                account_info.attrib[key] = val

    def _process_datev_xml_invoice_party(self, data):
        invoice_party = etree.SubElement(data["element"], "invoice_party")
        for key, val in self._prepare_datev_xml_invoice_party(data).items():
            if key == "vat_id":
                invoice_party.attrib[key] = data["key_apply"](
                    data["template_keys"], key, _float_to_string(val)
                )
            if key == "address":
                invoice_party.append(_etree_subelement(key, val))
            if key == "account":
                invoice_party.append(_etree_subelement(key, val))
            if key == "booking_info_bp":
                invoice_party.append(_etree_subelement(key, val))

    def _process_datev_xml_supplier_party(self, data):
        supplier_party = etree.SubElement(data["element"], "supplier_party")
        for key, val in self._prepare_datev_xml_supplier_party(data).items():
            if key == "vat_id":
                supplier_party.attrib[key] = data["key_apply"](
                    data["template_keys"], key, _float_to_string(val)
                )
            if key == "address":
                supplier_party.append(_etree_subelement(key, val))
            if key == "account":
                supplier_party.append(_etree_subelement(key, val))
            if key == "booking_info_bp":
                supplier_party.append(_etree_subelement(key, val))

    def _process_datev_xml_payment_conditions(self, data):
        if data["mode"] == "extended" and self.invoice_payment_term_id:
            payment_conditions = etree.SubElement(data["element"], "payment_conditions")
            for key, val in self._prepare_datev_xml_payment_conditions(data).items():
                payment_conditions.attrib[key] = data["key_apply"](
                    data["template_keys"], key, _float_to_string(val)
                )

    def _process_datev_xml_invoice_item_list(self, data):
        for item in self._prepare_datev_xml_invoice(data):
            invoice_item_list = etree.SubElement(data["element"], "invoice_item_list")
            for key, val in item.items():
                if key == "description_short":
                    invoice_item_list.attrib[key] = data["key_apply"](
                        data["template_keys"], key, _float_to_string(val)
                    )
                if key == "quantity":
                    invoice_item_list.attrib[key] = data["key_apply"](
                        data["template_keys"], key, _float_to_string(val)
                    )
                if key == "price_line_amount":
                    invoice_item_list.append(_etree_subelement(key, val))
                if key == "accounting_info":
                    invoice_item_list.append(_etree_subelement(key, val))

    def _process_datev_xml_total_amount(self, data):
        total_amount = etree.SubElement(data["element"], "total_amount")
        for key, val in self._prepare_datev_xml_total_amount(data).items():
            if key != "tax_line":
                total_amount.attrib[key] = data["key_apply"](
                    data["template_keys"], key, _float_to_string(val)
                )
            if key == "tax_line":
                for line in val:
                    total_amount.append(_etree_subelement(key, line))

    def _process_datev_xml_additional_info_footer(self, data):
        if not self.narration:
            return
        narration = self.env["syscoon.financeinterface"].text_from_html(self.narration)
        if narration:
            vals = self._get_datev_xml_footer()
            if vals:
                additional_info_footer = etree.SubElement(
                    data["element"], "additional_info_footer"
                )
                additional_info_footer.attrib["type"] = data["key_apply"](
                    data["template_keys"], "type", vals["type"]
                )
                additional_info_footer.attrib["content"] = data["key_apply"](
                    data["template_keys"], "content", vals["context"]
                )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # ++++++++++++++++++++++ DATEV XML Preparing +++++++++++++++++
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _prepare_datev_xml_invoice(self, data):  # noqa: C901
        vals = []
        total_invoice_amount = 0.0
        checked_keys = [
            ("price_line_amount", "tax"),
            ("accounting_info", "account_no"),
            ("accounting_info", "cost_category_id"),
            ("accounting_info", "cost_category_id2"),
            ("accounting_info", "bu_code"),
        ]

        def is_matching(vals_1, vals_2):
            return all(
                vals_1[key].get(child_key) == vals_2[key].get(child_key)
                for key, child_key in checked_keys
            )

        for line in self.invoice_line_ids:
            if (
                line.display_type not in ["line_section", "line_note"]
                and line.price_subtotal != 0.0
            ):
                vals.append(line._prepare_datev_xml_invoice_line(data))
        if self.env.company.export_xml_group_lines and data["mode"] == "extended":
            new_vals = []
            for val in vals:
                if not any(is_matching(new_val, val) for new_val in new_vals):
                    new_vals.append(val)
                else:
                    for new_val in new_vals:
                        if not is_matching(new_val, val):
                            continue
                        new_val["description_short"] = _("Grouped Invoice Line")
                        new_val["quantity"] += val["quantity"]
                        amount_vals = val["price_line_amount"]
                        new_amount_vals = new_val["price_line_amount"]
                        gross_amount = amount_vals["gross_price_line_amount"]
                        net_amount = amount_vals["net_price_line_amount"]
                        if amount_vals.get("tax_amount"):
                            new_amount_vals["tax_amount"] += amount_vals["tax_amount"]
                        new_amount_vals["gross_price_line_amount"] += gross_amount
                        new_amount_vals["net_price_line_amount"] += net_amount
                        break
            for count, new_val in enumerate(new_vals):
                if new_val["price_line_amount"]["net_price_line_amount"] == 0.0:
                    new_vals.pop(count)
                    continue
                new_amount_vals = new_val["price_line_amount"]
                new_val["quantity"] = 1.0
                if new_amount_vals.get("tax_amount"):
                    new_val["price_line_amount"][
                        "gross_price_line_amount"
                    ] = self.currency_id.round(
                        new_val["price_line_amount"]["net_price_line_amount"]
                        * (100 + new_val["price_line_amount"]["tax"])
                        / 100
                    )
                    new_val["price_line_amount"]["tax_amount"] = (
                        new_val["price_line_amount"]["gross_price_line_amount"]
                        - new_val["price_line_amount"]["net_price_line_amount"]
                    )
                    if new_val["price_line_amount"].get("tax_amount") and float_repr(
                        new_val["price_line_amount"]["tax_amount"], 2
                    ) in ["0.00", "-0.00"]:
                        new_val["price_line_amount"].pop("tax_amount")
            vals = new_vals
        for val in vals:
            price_line_ammount = dict(val["price_line_amount"])
            if "gross_price_line_amount" in price_line_ammount:
                total_invoice_amount += val["price_line_amount"][
                    "gross_price_line_amount"
                ]
        if float_repr(total_invoice_amount, 2) != float_repr(self.amount_total, 2):
            sign = -1 if self.move_type in ["in_refund", "out_refund"] else 1
            difference = self.currency_id.round(
                total_invoice_amount - (self.amount_total * sign)
            )
            if vals:
                last_val = vals[-1]
                del vals[-1]
                if last_val["price_line_amount"].get("tax_amount"):
                    last_val["price_line_amount"]["tax_amount"] = self.currency_id.round(
                        last_val["price_line_amount"]["tax_amount"] - difference
                    )
                if last_val["price_line_amount"].get("gross_price_line_amount", 0.0):
                    last_val["price_line_amount"][
                        "gross_price_line_amount"
                    ] = self.currency_id.round(
                        last_val["price_line_amount"].get("gross_price_line_amount", 0.0)
                        - difference
                    )
                vals.append(last_val)
        return vals

    def _prepare_datev_xml_invoice_party(self, data):
        if self.move_type in ["out_invoice", "out_refund"]:
            partner = self.commercial_partner_id
            booking_info = True
        if self.move_type in ["in_invoice", "in_refund"]:
            partner = self.company_id.partner_id
            booking_info = False
        vals = {}
        if partner.vat and partner.vat[:2] in EU_VAT:
            vals["vat_id"] = partner.vat
        address_val = self._prepare_datev_xml_address_values(
            data, partner, check_for_ref=True
        )
        vals["address"] = address_val
        if data["mode"] == "extended" and booking_info:
            if (
                (bank := self.partner_bank_id)
                and bank.acc_type == "iban"
                and bank.bank_id.name
            ):
                vals["account"] = self._prepare_datev_xml_account_values(data, bank)
            code = partner.debitor_number or partner.property_account_receivable_id.code
            vals["booking_info_bp"] = {
                "bp_account_no": data["key_apply"](
                    data["template_keys"], "bp_account_no", code
                )
            }
        return vals

    def _prepare_datev_xml_supplier_party(self, data):
        if self.move_type in ["out_invoice", "out_refund"]:
            partner = self.company_id.partner_id
            booking_info = False
        if self.move_type in ["in_invoice", "in_refund"]:
            partner = self.commercial_partner_id
            booking_info = True
        vals = {}
        if partner.vat and partner.vat[:2] in EU_VAT:
            vals["vat_id"] = partner.vat
        address_val = self._prepare_datev_xml_address_values(data, partner)
        vals["address"] = address_val
        if data["mode"] == "extended" and booking_info:
            if (
                (bank := self.partner_bank_id)
                and bank.acc_type == "iban"
                and bank.bank_id.name
            ):
                vals["account"] = self._prepare_datev_xml_account_values(data, bank)
            code = partner.creditor_number or partner.property_account_payable_id.code
            vals.update(
                {
                    "booking_info_bp": {
                        "bp_account_no": data["key_apply"](
                            data["template_keys"], "bp_account_no", code
                        )
                    },
                    "party_id": data["key_apply"](
                        data["template_keys"], "party_id", code
                    ),
                }
            )
        return vals

    def _prepare_datev_xml_address_values(  # noqa: C901
        self, data, partner_id, check_for_ref=False
    ):
        vals = {}
        customer_number = (
            partner_id.customer_number if "customer_number" in partner_id._fields else ""
        )
        if partner_id.name:
            vals["name"] = partner_id.name[:50]
        elif partner_id.parent_id.name:
            vals["name"] = partner_id.parent_id.name[:50]
        if partner_id.street:
            vals["street"] = partner_id.street[:40]
        if partner_id.zip:
            vals["zip"] = partner_id.zip
        if partner_id.city:
            vals["city"] = partner_id.city
        if partner_id.country_id:
            vals["country"] = partner_id.country_id.code
        if data["mode"] == "extended":
            if partner_id.phone:
                vals["phone"] = partner_id.phone[:20]
            if (
                "ref" in partner_id._fields
                and partner_id.ref
                and (
                    not check_for_ref
                    or (check_for_ref and partner_id.ref != customer_number)
                )
            ):
                vals["party_id"] = partner_id.ref[:15]
        for key, val in vals.items():
            vals[key] = data["key_apply"](data["template_keys"], key, val)
        return vals

    def _prepare_datev_xml_account_values(self, data, partner_bank_id):
        vals = {}
        if partner_bank_id.sanitized_acc_number:
            vals["iban"] = partner_bank_id.sanitized_acc_number
        if partner_bank_id.bank_id.bic:
            vals["swiftcode"] = partner_bank_id.bank_id.bic
        if partner_bank_id.bank_id.name:
            vals["bank_name"] = partner_bank_id.bank_id.name[:27]
        for key, val in vals.items():
            vals[key] = data["key_apply"](data["template_keys"], key, val)
        return vals

    def _prepare_datev_xml_invoice_info(self, data):
        vals = {}
        vals["invoice_date"] = self.invoice_date
        if self.move_type in ["out_invoice", "in_invoice"]:
            vals["invoice_type"] = "Rechnung"
        if self.move_type in ["out_refund", "in_refund"]:
            vals["invoice_type"] = "Gutschrift/Rechnungskorrektur"
        vals["invoice_id"] = (self.datev_ref or "")[:36]
        vals["delivery_date"] = str(self.date)
        for key, val in vals.items():
            vals[key] = data["key_apply"](data["template_keys"], key, val)
        return vals

    def _prepare_datev_xml_accounting_info(self, data):
        vals = {}
        if self.move_type == "out_invoice":
            vals["booking_text"] = "Erlöse"
        if self.move_type == "out_refund":
            vals["booking_text"] = "Gutschrift Erlöse"
        if self.move_type == "in_invoice":
            vals["booking_text"] = "Aufwand"
        if self.move_type == "in_refund":
            vals["booking_text"] = "Gutschrift Aufwand"
        for key, val in vals.items():
            vals[key] = data["key_apply"](data["template_keys"], key, val)
        return vals

    def _prepare_datev_xml_total_amount(self, data):
        vals = {}
        total = (
            -self.amount_total
            if self.move_type in ["out_refund", "in_refund"]
            else self.amount_total
        )
        vals["total_gross_amount_excluding_third-party_collection"] = total
        if data["mode"] == "extended":
            if self.move_type in ["out_refund", "in_refund"]:
                vals["net_total_amount"] = -self.amount_untaxed
            else:
                vals["net_total_amount"] = self.amount_untaxed
        vals["currency"] = self.currency_id.name or "EUR"
        tax_lines = self.line_ids.filtered(lambda line: line.tax_line_id)
        tax_key_lines = self.line_ids.filtered(lambda line: line.tax_ids)
        currency_rate = 1.0
        if self.currency_id and self.currency_id != self.env.company.currency_id:
            currency_rate = self.company_id.currency_id._convert(
                1.0, self.currency_id, self.company_id, self.date, round=False
            )
        result = {}
        done_taxes = set()
        for line in tax_lines:
            result.setdefault(
                line.tax_line_id.tax_group_id,
                {"rate": 0.0, "base": 0.0, "amount": 0.0, "currency_amount": 0.0},
            )
            result[line.tax_line_id.tax_group_id]["rate"] = line.tax_line_id.amount
            result[line.tax_line_id.tax_group_id]["amount"] += abs(line.balance)
            tax_key_add_base = (line.tax_line_id.id,)
            base_amount = line.tax_base_amount * currency_rate
            if tax_key_add_base not in done_taxes:
                # The base should be added ONCE
                result[line.tax_line_id.tax_group_id]["base"] += base_amount
                done_taxes.add(tax_key_add_base)
        for line in tax_key_lines:
            result.setdefault(
                line.tax_ids[0].tax_group_id,
                {"rate": 0.0, "base": 0.0, "amount": 0.0, "currency_amount": 0.0},
            )
            if line.tax_ids[0].amount == 0.0:
                result[line.tax_ids[0].tax_group_id]["base"] += (
                    -line.debit + line.credit
                ) * currency_rate
                result[line.tax_ids[0].tax_group_id][
                    "currency_amount"
                ] += -line.amount_currency
        vals["tax_line"] = self._prepare_datev_xml_tax_line(data, currency_rate, result)
        if not vals["tax_line"]:
            line_vals = {}
            line_vals["tax"] = 0.0
            line_vals["currency"] = self.currency_id.name
            vals["tax_line"].append(line_vals)
        return vals

    def _prepare_datev_xml_tax_line(self, data, currency_rate, result_values):
        value_list = []
        result_values = sorted(result_values.items(), key=lambda l: l[0].sequence)
        for _group, amounts in result_values:
            line_vals = {}
            line_vals["tax"] = amounts["rate"]
            line_vals["currency"] = self.currency_id.name
            if amounts["rate"] != 0.0:
                currency_rate = 1.0
            if (
                amounts["currency_amount"]
                and amounts["base"] != amounts["currency_amount"]
            ):
                amounts["base"] = amounts["currency_amount"]
            if data["mode"] == "extended":
                if self.move_type in ["out_refund", "in_refund"]:
                    line_vals["net_price_line_amount"] = -amounts["base"]
                    line_vals["gross_price_line_amount"] = -amounts["base"] + (
                        amounts["amount"] * currency_rate
                    )
                else:
                    line_vals["net_price_line_amount"] = amounts["base"]
                    line_vals["gross_price_line_amount"] = amounts["base"] + (
                        amounts["amount"] * currency_rate
                    )
                if amounts["amount"] > 0.0:
                    if self.move_type in ["out_refund", "in_refund"]:
                        line_vals["tax_amount"] = -amounts["amount"]
                    else:
                        line_vals["tax_amount"] = amounts["amount"]
            value_list.append(line_vals)
        return value_list

    def _prepare_datev_xml_payment_conditions(self, data):
        vals = {}
        payment_term = self.invoice_payment_term_id
        vals["currency"] = self.currency_id.name
        vals["due_date"] = self.invoice_date_due
        vals["payment_conditions_text"] = payment_term.name
        if payment_term.datev_payment_conditons_id:
            vals["payment_conditions_id"] = payment_term.datev_payment_conditons_id
        for key, val in vals.items():
            vals[key] = data["key_apply"](data["template_keys"], key, val)
        return vals

    def _get_datev_xml_document_value(self):
        if self.move_type in ["out_invoice", "out_refund"]:
            return "Outgoing"
        return "Incoming"

    def _get_datev_xml_footer(self):
        text = self.env["syscoon.financeinterface"].text_from_html(
            self.narration, max_chars=60
        )
        if text:
            return False
        return {"type": "text", "context": text}


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_datev_xml_invoice_line(self, data):  # noqa: C901
        name = self.name[:40] if self.name else _("Description")
        item = {
            "description_short": data["key_apply"](
                data["template_keys"], "description_short", name
            ),
            "quantity": self.quantity if self.quantity else 1.0,
            "price_line_amount": {"tax": self.tax_ids[:1].amount},
        }
        if data["mode"] != "extended":
            return item
        tax_amount = self.move_id.currency_id.round(
            self.price_total - self.price_subtotal
        )
        sign = 1
        if self.move_id.move_type in ["out_refund", "in_refund"]:
            sign = -1
        if tax_amount != 0.0:
            item["price_line_amount"]["tax_amount"] = sign * tax_amount
        item["price_line_amount"].update(
            {
                "gross_price_line_amount": sign * self.price_total,
                "net_price_line_amount": sign * self.price_subtotal,
                "currency": self.currency_id.name or "EUR",
            }
        )
        code = self.account_id.code
        item["accounting_info"] = {
            "account_no": code.lstrip("0") if code else "",
            "bu_code": False,
        }
        if (
            self.currency_id
            and self.currency_id != self.company_id.currency_id
            and self.amount_currency != 0.0
        ):
            exchange_rate = self.amount_currency / self.balance
            item["accounting_info"]["exchange_rate"] = f"{exchange_rate:.4f}00"
        name = data["key_apply"](
            data["template_keys"], "booking_text", self.name or _("Description")
        )
        item["accounting_info"].update(
            {
                "bu_code": False,
                "booking_text": (name or "")[:60],
            }
        )
        tax_key = self.tax_ids[:1].datev_tax_key
        if not self.account_id.datev_automatic_account and tax_key != "0":
            item["accounting_info"]["bu_code"] = tax_key
        if not self.move_id.company_id.export_xml_analytic_accounts:
            return item
        for analytic in self._fetch_analytic_accounts():
            code = analytic.code or analytic.name or ""
            analytic_key = "cost_category_id"
            if analytic.plan_id.datev_cost_center == "add_to_kost1":
                analytic_key = "cost_category_id"
            elif analytic.plan_id.datev_cost_center == "add_to_kost2":
                analytic_key = "cost_category_id2"
            if analytic_key:
                code = data["key_apply"](data["template_keys"], analytic_key, code)
                item["accounting_info"][analytic_key] = (code or "").strip()[:36]
        return item
