# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import base64
import csv
import logging
import time
from datetime import datetime
from functools import lru_cache
from io import StringIO

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

ACCOUNT_TYPES = [
    "asset_receivable",
    "asset_cash",
    "asset_current",
    "asset_non_current",
    "asset_prepayments",
    "asset_fixed",
    "liability_payable",
    "liability_credit_card",
    "liability_current",
    "liability_non_current",
    "equity",
    "equity_unaffected",
    "off_balance",
]

COST_ACCOUNT_TYPES = [
    "income",
    "income_other",
    "expense",
    "expense_depreciation",
    "expense_direct_cost",
]

NO_TAX_ACCOUNT_TYPES = [
    "asset_receivable",
    "asset_cash",
    "liability_payable",
    "liability_credit_card",
    "liability_current",
    "liability_non_current",
    "equity",
    "equity_unaffected",
    "off_balance",
]


class ImportDatev(models.Model):
    """
    The class syscoon.datev.import is for the import of
    DATEV Buchungsstapel (account.moves)
    """

    _name = "syscoon.datev.import"
    _order = "name desc"
    _description = "DATEV ASCII-Import"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        readonly=True,
        default=lambda self: self.env["ir.sequence"].get("syscoon.datev.import.sequence")
        or "-",
    )
    description = fields.Char(required=True)
    template_id = fields.Many2one("syscoon.datev.import.config", string="Import Template")
    journal_id = fields.Many2one("account.journal", required=True)
    one_move = fields.Boolean("In one move?")
    start_date = fields.Date(required=True, default=fields.Date.today())
    end_date = fields.Date(required=True, default=fields.Date.today())
    log_line = fields.One2many("syscoon.datev.import.log", "parent_id", "Log")
    account_move_ids = fields.One2many(
        "account.move", "syscoon_datev_import_id", "Account Moves"
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("error", "Error"),
            ("imported", "Imported"),
            ("booked", "Booked"),
        ],
        "Status",
        index=True,
        readonly=True,
        default="draft",
        tracking=True,
    )

    def start_import(self):
        """Initial function for manage the import of DATEV-moves"""
        # if self.account_move_ids:
        #    self.reset_import()
        self.env["syscoon.datev.import.log"].create(
            {"parent_id": self.id, "name": _("Import started"), "state": "info"}
        )
        move_values = {}
        log_error = False
        file = self.get_attachment()
        if self.get_import_config()["remove_datev_header"]:
            file = self.remove_datev_header(file)
        import_list = self.convert_lines(file)
        log_vals = []
        for log in self.check_can_created(import_list):
            if log["state"] == "error":
                log_error = True
            log_vals.append(
                {
                    "parent_id": log["parent_id"],
                    "line": log["line"],
                    "name": log["name"],
                    "state": log["state"],
                }
            )
        if log_vals:
            self.env["syscoon.datev.import.log"].create(log_vals)
        if log_error:
            self.write({"state": "error"})
        if not log_error:
            move_values = self.create_values(import_list)
        self._process_move_creation(move_values)
        self.env["syscoon.datev.import.log"].create(
            {
                "parent_id": self.id,
                "name": _("Import done"),
                "state": "info",
            }
        )

    def _process_move_creation(self, move_values):
        if not move_values:
            return
        self.create_moves(move_values)
        self.write({"state": "imported"})
        if self.template_id.auto_reconcile or self.template_id.post_moves:
            self.confirm_moves()
        if self.template_id.auto_reconcile:
            if not self.template_id.discount_account_income:
                self.env["syscoon.datev.import.log"].create(
                    {
                        "parent_id": self.id,
                        "name": _("Income Discount Account not selected in Template!"),
                        "state": "error",
                    }
                )
                self.write({"state": "error"})
            elif not self.template_id.discount_account_expenses:
                self.env["syscoon.datev.import.log"].create(
                    {
                        "parent_id": self.id,
                        "name": _("Expense Discount Account not selected in Template!"),
                        "state": "error",
                    }
                )
                self.write({"state": "error"})
            else:
                self.reconcile_moves()

    def reset_import(self):
        for move in self.account_move_ids:
            move.line_ids.remove_move_reconcile()
        if self.account_move_ids:
            self.account_move_ids.unlink()
        if self.log_line:
            self.log_line.unlink()
        self.write({"state": "draft"})

    def confirm_moves(self):
        if self.state == "imported":
            if self.account_move_ids:
                self.account_move_ids.action_post()
                self.write({"state": "booked"})
            self.env["syscoon.datev.import.log"].create(
                {
                    "parent_id": self.id,
                    "name": _("Moves confirmed"),
                    "state": "info",
                }
            )

    def reconcile_moves(self):  # noqa: C901
        for move in self.account_move_ids:
            reconcile_lines = move._prepare_datev_reconcile_lines()
            if len(reconcile_lines) > 1:
                for line in reconcile_lines:
                    reconciled = bool(line.reconciled)
                if not reconciled:
                    reconcile_lines.reconcile()
                self.env["syscoon.datev.import.log"].create(
                    {
                        "parent_id": self.id,
                        "name": _("Move %s reconciled", move.ref),
                        "state": "info",
                    }
                )
            if len(reconcile_lines) == 1:
                self.env["syscoon.datev.import.log"].create(
                    {
                        "parent_id": self.id,
                        "name": _("Move %s not reconciled", move.ref),
                        "state": "warning",
                    }
                )

    def get_attachment(self):
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "syscoon.datev.import"),
                ("res_id", "=", self.id),
            ]
        )
        if not attachment:
            raise UserError(_("No Import File uploaded, please upload one!"))
        if len(attachment) == 1:
            file = base64.decodebytes(attachment.datas)
            file = file.decode(self.get_import_config()["encoding"])
            return file
        raise UserError(
            _(
                "There is more than one file attached to this record. "
                "Please make sure that there is only one attached CSV-file."
            )
        )

    def get_import_config(self):
        if not self.template_id:
            raise UserError(_("There is no Import Template for this company!"))
        return {
            "delimiter": str(self.template_id.delimiter),
            "encoding": self.template_id.encoding,
            "quotechar": str(self.template_id.quotechar),
            "headerrow": self.template_id.headerrow,
            "remove_datev_header": self.template_id.remove_datev_header,
            "journal_id": self.journal_id.id,
            "company_id": self.company_id.id,
            "company_currency_id": self.env.company.currency_id.id,
            "discount_account_income": self.template_id.discount_account_income,
            "discount_account_expenses": self.template_id.discount_account_expenses,
            "date": self.start_date,
            "ref": self.template_id.ref,
            "post": self.template_id.post_moves,
            "auto_reconcile": self.template_id.auto_reconcile,
            "payment_difference_handling": self.template_id.payment_difference_handling,
        }

    def get_import_struct(self):
        struct = {}
        for row in self.template_id.import_config_row_ids:
            struct[row.name] = {
                "type": row.assignment_type,
                "field_type": row.assignment_type.field_type,
                "object": row.assignment_type.object,
                "field": row.assignment_type.field,
                "domain": row.assignment_type.domain,
                "default": row.assignment_type.default,
                "account_move_field": row.assignment_type.account_move_field,
                "account_move_line_field": row.assignment_type.account_move_line_field,
                "padding": row.assignment_type.padding,
                "date_format": row.assignment_type.date_format,
                "decimal_sign": row.assignment_type.decimal_sign,
                "skip_at": row.assignment_type.skip_at,
                "required": row.required,
                "skip": row.skip,
                "import_value": False,
            }
        return struct

    def remove_datev_header(self, file):
        file = file[file.index("\n") + 1 :]
        return file

    def convert_lines(self, file):
        config = self.get_import_config()
        reader = csv.DictReader(
            StringIO(file), delimiter=config["delimiter"], quotechar=config["quotechar"]
        )
        pre_import_list = []
        for row in reader:
            pre_import_list.append(dict(row))
        import_list = []
        struct = self.get_import_struct()
        for row in pre_import_list:
            new_row = {}
            for key, value in row.items():
                if key not in struct:
                    continue
                struct_values = struct[key].copy()
                struct_values["import_value"] = value
                new_row[key] = struct_values
            import_list.append(new_row)
        return import_list

    def check_can_created(self, vals_list):
        logs = []
        count = 1
        for values in vals_list:
            logs += self.check_required_fields(values, count)
            count += 1
        count = 1
        for values in vals_list:
            logs += self.check_values(values, count)
            count += 1
        return logs

    def check_required_fields(self, values, count):
        logs = []
        required_types = [
            "amount",
            "move_sign",
            "account",
            "counteraccount",
            "move_date",
        ]
        template_required = self.template_id.import_config_row_ids.search(
            [("required", "=", True)]
        )
        for template in template_required:
            if template.assignment_type.type not in required_types:
                required_types.append(template.assignment_type.type)
        for k, v in values.items():
            _logger.info(k, v)
            if (v["type"].type in required_types and v["import_value"]) or (
                v["type"].type == "tax_key"
                and v["type"].type in required_types
                and not v["import_value"]
            ):
                required_types.remove(v["type"].type)
        for required_type in required_types:
            field = dict(
                self.env["syscoon.datev.import.assignment"]
                ._fields["type"]
                ._description_selection(self.env)
            )[required_type]
            logs.append(
                {
                    "parent_id": self.id,
                    "line": count,
                    "name": _("Missing Required Field %s.", field),
                    "state": "error",
                }
            )
        return logs

    def check_values(self, values, count):  # noqa: C901
        logs = []
        for k, v in values.items():
            if v["field_type"] == "decimal":
                try:
                    self.convert_to_float(v["import_value"])
                except Exception:
                    logs.append(
                        {
                            "parent_id": self.id,
                            "line": count,
                            "name": _("%s cant be converted.", k),
                            "state": "error",
                        }
                    )
            if v["type"].type == "move_sign":
                try:
                    self.check_move_sign(v["import_value"])
                except Exception:
                    logs.append(
                        {
                            "parent_id": self.id,
                            "line": count,
                            "name": _("%s does not exist. It must be S or H.", k),
                            "state": "error",
                        }
                    )
            if v["type"].object and v["import_value"]:
                try:
                    self.get_object(
                        v["type"].object,
                        v["type"].field,
                        v["import_value"],
                        v["padding"],
                    )
                except Exception:
                    logs.append(
                        {
                            "parent_id": self.id,
                            "line": count,
                            "name": _("%s does not exist. Please Check.", k),
                            "state": "error",
                        }
                    )
            if v["type"].type == "account":
                partner = self.env["res.partner"]
                partner_check = False
                account_id = self.get_object(
                    v["type"].object, v["type"].field, v["import_value"], v["padding"]
                )
                if not account_id:
                    partner_debit_id = partner.search(
                        [("debitor_number", "=", v["import_value"])]
                    )
                    partner_credit_id = partner.search(
                        [("creditor_number", "=", v["import_value"])]
                    )
                    if partner_debit_id or partner_credit_id:
                        partner_check = True
                    if not partner_check:
                        logs.append(
                            {
                                "parent_id": self.id,
                                "line": count,
                                "name": _(
                                    "%s does not exist. Please Check.",
                                    v["import_value"],
                                ),
                                "state": "error",
                            }
                        )
            if v["type"].type == "counteraccount":
                partner = self.env["res.partner"]
                partner_check = False
                account_id = self.get_object(
                    v["type"].object, v["type"].field, v["import_value"], v["padding"]
                )
                if not account_id:
                    partner_debit_id = partner.search(
                        [("debitor_number", "=", v["import_value"])]
                    )
                    partner_credit_id = partner.search(
                        [("creditor_number", "=", v["import_value"])]
                    )
                    if partner_debit_id or partner_credit_id:
                        partner_check = True
                    if not partner_check:
                        logs.append(
                            {
                                "parent_id": self.id,
                                "line": count,
                                "name": _(
                                    "%s does not exist. Please Check.",
                                    v["import_value"],
                                ),
                                "state": "error",
                            }
                        )
            if v["type"].type == "move_date":
                try:
                    datetime.strptime(v["import_value"], v["date_format"])
                except Exception:
                    logs.append(
                        {
                            "parent_id": self.id,
                            "line": count,
                            "name": _(
                                "%(key)s does not fit to %(value)s. Please Check.",
                                key=k,
                                value=v["date_format"],
                            ),
                            "state": "error",
                        }
                    )
            if v["type"].type == "guid":
                created_guid = self.env["account.move"].search(
                    [("syscoon_datev_import_guid", "=", v["import_value"])]
                )
                if created_guid:
                    logs.append(
                        {
                            "parent_id": self.id,
                            "line": count,
                            "name": _(
                                "%(key)s with GUID %(value)s already exist and can not be imported",
                                key=k,
                                value=v["import_value"],
                            ),
                            "state": "warning",
                        }
                    )
        return logs

    def convert_to_float(self, value):
        if value == "":
            return True
        value = value.replace(".", "")
        value = value.replace(",", ".")
        return float(value)

    def check_move_sign(self, value):
        if value.lower() in ["s", "h"]:
            return value.lower()
        return False

    def get_date(self, dt_format, value):
        move_date = datetime.strptime(value, dt_format)
        if "%y" not in dt_format or "%Y" not in dt_format:
            move_date = move_date.replace(year=self.end_date.year)
        return move_date

    def get_object(self, model_obj, field, value, padding, domain=None):
        if not isinstance(domain, list):
            try:
                domain = safe_eval(domain) if isinstance(domain, str) else []
            except Exception:
                domain = []
        return_object = False
        if model_obj == "account.tax":
            domain += [(field, "=", value), ("company_id", "=", self.company_id.id)]
            taxes = self.env[model_obj].search(domain)
            return_object = taxes[:1]
        elif model_obj == "account.account":
            if padding:
                return_object = self.env[model_obj].search(
                    domain
                    + [
                        (field, "=", value.zfill(padding)),
                        ("company_ids", "in", [self.company_id.id]),
                    ]
                )
            else:
                return_object = self.env[model_obj].search(
                    domain
                    + [(field, "=", value), ("company_ids", "in", [self.company_id.id])]
                )
        elif padding:
            return_object = self.env[model_obj].search(
                domain + [(field, "=", value.zfill(padding))]
            )
        else:
            return_object = self.env[model_obj].search(domain + [(field, "=", value)])
        return return_object

    def _prepare_default_move_values(self):
        move = {
            "ref": False,
            "date": False,
            "company_id": self.company_id.id,
            "journal_id": self.journal_id.id,
            "line_ids": [(0, 0, [])],
            "move_type": "entry",
            "syscoon_datev_import_id": self.id,
        }
        debit_line = {
            "account_id": False,
            "partner_id": False,
            "name": False,
            "analytic_distribution": {},
            "tax_ids": [],
            "tax_line_id": False,
            "debit": 0.0,
            "credit": 0.0,
            "tax_tag_ids": False,
        }
        credit_line = {
            "account_id": False,
            "partner_id": False,
            "name": False,
            "analytic_distribution": {},
            "tax_ids": [],
            "tax_line_id": False,
            "debit": 0.0,
            "credit": 0.0,
            "tax_tag_ids": False,
        }
        discount_line = {
            "account_id": False,
            "partner_id": False,
            "name": False,
            "analytic_distribution": False,
            "tax_ids": [],
            "tax_line_id": False,
            "debit": 0.0,
            "credit": 0.0,
            "tax_tag_ids": False,
        }
        return {
            "move": move,
            "debit_line": debit_line,
            "credit_line": credit_line,
            "discount_line": discount_line,
        }

    def _get_analytic_account(self, account_id, cost_center, values):
        if account_id.account_type not in COST_ACCOUNT_TYPES:
            return self.env["account.analytic.account"]
        return self.get_object(
            values["type"].object,
            values["type"].field,
            values["import_value"],
            values["padding"],
        ).filtered(lambda x: x.plan_id.datev_cost_center == cost_center)

    def _get_tax(self, account_id):
        tax_id = False
        if account_id.datev_automatic_tax:
            tax_ids = account_id.datev_automatic_tax
            for tax in tax_ids:
                if tax.price_include:
                    tax_id = tax
            if account_id.datev_vatid_required and len(tax_ids) == 1:
                tax_id = tax_ids[0]
        return tax_id

    def _is_cost_account(self, account_id):
        return account_id and account_id.account_type in COST_ACCOUNT_TYPES

    def create_values(self, vals_list):  # noqa: C901
        @lru_cache
        def _partner(field_key, number):
            return partner.search([(f"{field_key}_number", "=", number)], limit=1)

        moves = []
        partner = self.env["res.partner"]
        move_obj = self.env["account.move"]
        company_currency = self.company_id.currency_id.name

        for values in vals_list:
            default_values = self._prepare_default_move_values()
            move = default_values["move"]
            debit_line = default_values["debit_line"]
            credit_line = default_values["credit_line"]
            discount_line = default_values["discount_line"]

            sign = "s"
            has_currency = False
            taxes = False
            tax_id = False
            tax_direction = False
            for _k, v in values.items():
                if v["type"].type == "move_sign":
                    sign = self.check_move_sign(v["import_value"])
                elif v["type"].type == "currency" and v["import_value"]:
                    has_currency = v["import_value"] != company_currency
                elif v["type"].type == "move_date":
                    move["date"] = self.get_date(v["date_format"], v["import_value"])
                elif v["type"].type == "move_name":
                    move["ref"] = v["import_value"]
                elif v["type"].type == "move_ref":
                    debit_line["name"] = v["import_value"]
                    credit_line["name"] = v["import_value"]
                elif v["type"].type == "guid":
                    move["syscoon_datev_import_guid"] = v["import_value"]

            amount_key = "base_amount" if has_currency else "amount"
            for _k, v in values.items():
                if v["type"].type == amount_key:
                    amount_value = self.convert_to_float(v["import_value"])
                    debit_key, credit_key = (
                        ("debit", "credit") if sign == "s" else ("credit", "debit")
                    )
                    debit_line[debit_key] = amount_value
                    credit_line[credit_key] = amount_value

            for _k, v in values.items():
                if v["type"].type == "account":
                    debit_line["account_id"] = self.get_object(
                        v["type"].object,
                        v["type"].field,
                        v["import_value"],
                        v["padding"],
                    )
                    if self._is_cost_account(debit_line["account_id"]):
                        tax_direction = "debit_line"
                    tax_id = self._get_tax(debit_line["account_id"])
                    if not debit_line["account_id"]:
                        partner_debit_id = _partner("debitor", v["import_value"])
                        partner_credit_id = _partner("creditor", v["import_value"])
                        if partner_debit_id:
                            debit_line["account_id"] = (
                                partner_debit_id.property_account_receivable_id
                            )
                            debit_line["partner_id"] = partner_debit_id.id
                            credit_line["partner_id"] = partner_debit_id.id
                        if partner_credit_id:
                            debit_line["account_id"] = (
                                partner_credit_id.property_account_payable_id
                            )
                            debit_line["partner_id"] = partner_credit_id.id
                            credit_line["partner_id"] = partner_credit_id.id
                if v["type"].type == "counteraccount":
                    credit_line["account_id"] = self.get_object(
                        v["type"].object,
                        v["type"].field,
                        v["import_value"],
                        v["padding"],
                    )
                    if self._is_cost_account(credit_line["account_id"]):
                        tax_direction = "credit_line"
                    tax_id = self._get_tax(credit_line["account_id"])
                    if not credit_line["account_id"]:
                        partner_debit_id = _partner("debitor", v["import_value"])
                        partner_credit_id = _partner("creditor", v["import_value"])
                        if len(partner_credit_id) > 1:
                            raise UserError(
                                _(
                                    "There are multiple partners with same creditor "
                                    "number %s.",
                                    v["import_value"],
                                )
                            )
                        if partner_credit_id:
                            credit_line["account_id"] = (
                                partner_credit_id.property_account_payable_id
                            )
                            credit_line["partner_id"] = partner_credit_id.id
                            debit_line["partner_id"] = partner_credit_id.id
                        if len(partner_debit_id) > 1:
                            raise UserError(
                                _(
                                    "There are multiple partners with same "
                                    "debitor number %s.",
                                    v["import_value"],
                                )
                            )
                        if partner_debit_id:
                            credit_line["account_id"] = (
                                partner_debit_id.property_account_receivable_id
                            )
                            credit_line["partner_id"] = partner_debit_id.id
                            debit_line["partner_id"] = partner_debit_id.id
                    if tax_id and not tax_direction:
                        tax_direction = "credit_line"

            for _k, v in values.items():
                if v["type"].type == "tax_key" and v["import_value"]:
                    if v["import_value"] != "40":
                        tax_id = self.get_object(
                            v["type"].object,
                            v["type"].field,
                            v["import_value"],
                            v["padding"],
                            domain=v["type"].domain,
                        )
                    else:
                        if (
                            debit_line["account_id"]
                            and tax_direction in ("debit_line", "credit_line")
                            and debit_line["account_id"].datev_automatic_tax
                            and debit_line["account_id"].datev_no_tax
                        ):
                            tax_id = self.env["account.tax"]

                elif v["type"].type == "tax_key" and not v["import_value"]:
                    if (debit_line["account_id"] and tax_direction == "debit_line") and (
                        debit_line["account_id"].datev_automatic_tax
                        and debit_line["account_id"].datev_automatic_tax
                        and not debit_line["account_id"].datev_no_tax
                    ):
                        tax_id = debit_line["account_id"].datev_automatic_tax.filtered(
                            lambda x: x.price_include is True
                        )
                    if (
                        credit_line["account_id"] and tax_direction == "credit_line"
                    ) and (
                        credit_line["account_id"].datev_automatic_tax
                        and credit_line["account_id"].datev_automatic_tax
                        and not credit_line["account_id"].datev_no_tax
                    ):
                        tax_id = credit_line["account_id"].datev_automatic_tax.filtered(
                            lambda x: x.price_include is True
                        )
                if v["type"].type in ("cost1", "cost2") and v["import_value"]:
                    cost_key = {"cost1": "add_to_kost1", "cost2": "add_to_kost2"}.get(
                        v["type"].type
                    )
                    if debit_analytic := self._get_analytic_account(
                        debit_line["account_id"], cost_key, v
                    ):
                        debit_line["analytic_distribution"][str(debit_analytic.id)] = 100
                    if credit_analytic := self._get_analytic_account(
                        credit_line["account_id"], cost_key, v
                    ):
                        credit_line["analytic_distribution"][
                            str(credit_analytic.id)
                        ] = 100
            account_with_tax = any(
                (
                    credit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES,
                    debit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES,
                )
            )
            if tax_id and account_with_tax:
                if debit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES:
                    tax_direction = "debit_line"
                if credit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES:
                    tax_direction = "credit_line"

                if not tax_direction:
                    if debit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES:
                        tax_direction = "debit_line"
                    if credit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES:
                        tax_direction = "credit_line"
                if (
                    debit_line["account_id"].account_type not in NO_TAX_ACCOUNT_TYPES
                    and tax_direction == "debit_line"
                ):
                    if debit_line["debit"]:
                        taxes = tax_id.compute_all(debit_line["debit"])
                        debit_line["debit"] = taxes["total_excluded"]
                    if debit_line["credit"]:
                        taxes = tax_id.compute_all(debit_line["credit"])
                        debit_line["credit"] = taxes["total_excluded"]
                    debit_line["tax_ids"] = [(6, 0, tax_id.ids)]
                    if taxes and taxes.get("base_tags", False):
                        debit_line["tax_tag_ids"] = [(6, 0, taxes["base_tags"])]
                if (
                    credit_line["account_id"].account_type in COST_ACCOUNT_TYPES
                    and tax_direction == "credit_line"
                ):
                    if credit_line["debit"]:
                        taxes = tax_id.compute_all(credit_line["debit"])
                        credit_line["debit"] = taxes["total_excluded"]
                    if credit_line["credit"]:
                        taxes = tax_id.compute_all(credit_line["credit"])
                        credit_line["credit"] = taxes["total_excluded"]
                    credit_line["tax_ids"] = [(6, 0, tax_id.ids)]
                    if taxes and taxes.get("base_tags", False):
                        credit_line["tax_tag_ids"] = [(6, 0, taxes["base_tags"])]

            for _k, v in values.items():
                if v["type"].type == "discount_amount" and v["import_value"]:
                    discount_line["name"] = _("Discount")
                    amount = self.convert_to_float(v["import_value"])
                    if move["ref"] not in ("0", False):
                        opposite_move = move_obj._get_opposite_datev_moves(
                            ref=move["ref"]
                        )
                        for line in opposite_move.line_ids:
                            if (
                                line.account_id.account_type in COST_ACCOUNT_TYPES
                                and line.tax_ids
                            ):
                                tax_id = line.tax_ids[0].with_context(
                                    force_price_include=True
                                )
                    if tax_id:
                        if tax_id.datev_discount_account:
                            for tax in tax_id.datev_discount_account.datev_automatic_tax:
                                if tax.price_include:
                                    tax_id = tax
                        taxes = tax_id.compute_all(amount)
                        discount_line["account_id"] = tax_id.datev_discount_account.id
                        if debit_line["account_id"].account_type in [
                            "asset_receivable",
                            "liability_payable",
                        ]:
                            if debit_line["credit"]:
                                discount_line["debit"] = taxes["total_excluded"]
                                debit_line["credit"] += amount
                            if debit_line["debit"]:
                                discount_line["credit"] = taxes["total_excluded"]
                                debit_line["debit"] += amount
                        if credit_line["account_id"].account_type in [
                            "asset_receivable",
                            "liability_payable",
                        ]:
                            if credit_line["credit"]:
                                discount_line["debit"] = taxes["total_excluded"]
                                credit_line["credit"] += amount
                            if credit_line["debit"]:
                                discount_line["credit"] = taxes["total_excluded"]
                                credit_line["debit"] += amount
                        discount_line["tax_ids"] = [(6, 0, tax_id.ids)]
                        discount_line["tax_tag_ids"] = [(6, 0, taxes["base_tags"])]

            if not isinstance(debit_line["account_id"], int):
                debit_line["account_id"] = debit_line["account_id"].id
            if not isinstance(credit_line["account_id"], int):
                credit_line["account_id"] = credit_line["account_id"].id
            move["line_ids"] = [(0, 0, debit_line), (0, 0, credit_line)]

            if discount_line["name"]:
                move["line_ids"].append((0, 0, discount_line))

            if taxes:
                for tax in taxes["taxes"]:
                    if not tax["account_id"]:
                        continue
                    tax_move_line = {
                        "account_id": tax["account_id"],
                        "name": tax["name"],
                        "tax_base_amount": tax["base"],
                        "tax_tag_ids": [(6, 0, tax["tag_ids"])],
                        "tax_line_id": tax["id"],
                        "tax_group_id": tax_id.tax_group_id.id,
                        "tax_repartition_line_id": tax["tax_repartition_line_id"],
                    }

                    partner_debit_id = partner.search(
                        [
                            ("debitor_number", "!=", False),
                            ("debitor_number", "=", v["import_value"]),
                        ],
                        limit=1,
                    )
                    partner_credit_id = partner.search(
                        [
                            ("creditor_number", "!=", False),
                            ("creditor_number", "=", v["import_value"]),
                        ],
                        limit=1,
                    )

                    if debit_line["tax_ids"]:
                        if debit_line["debit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["credit"] = -tax["amount"]
                            else:
                                tax_move_line["debit"] = tax["amount"]
                        if debit_line["credit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["debit"] = -tax["amount"]
                            else:
                                tax_move_line["credit"] = tax["amount"]
                        tax_move_line["partner_id"] = debit_line["partner_id"]
                    if credit_line["tax_ids"]:
                        if credit_line["debit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["credit"] = -tax["amount"]
                            else:
                                tax_move_line["debit"] = tax["amount"]
                        if credit_line["credit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["debit"] = -tax["amount"]
                            else:
                                tax_move_line["credit"] = tax["amount"]
                        tax_move_line["partner_id"] = credit_line["partner_id"]
                    if discount_line["tax_ids"]:
                        if discount_line["debit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["credit"] = -tax["amount"]
                            else:
                                tax_move_line["debit"] = tax["amount"]
                        if discount_line["credit"]:
                            if tax["amount"] < 0.0:
                                tax_move_line["debit"] = -tax["amount"]
                            else:
                                tax_move_line["credit"] = tax["amount"]
                        tax_move_line["partner_id"] = discount_line["partner_id"]
                    move["line_ids"].append((0, 0, tax_move_line))
            for ml in move["line_ids"]:
                line_vals = ml[2] if len(ml) == 3 else {}
                remove = False
                if (
                    not line_vals.get("account_id")
                    and self.template_id.ignore_incomplete_moves
                ):
                    remove = True
                    self.env["syscoon.datev.import.log"].create(
                        {
                            "parent_id": self.id,
                            "name": _("Move %s not imported", move["ref"]),
                            "state": "warning",
                        }
                    )
            existing_guid = False
            if move.get("syscoon_datev_import_guid"):
                existing_guid = self.env["account.move"].search(
                    [
                        (
                            "syscoon_datev_import_guid",
                            "=",
                            move["syscoon_datev_import_guid"],
                        )
                    ]
                )
            if not remove and not existing_guid:
                moves.append(move)
        return moves

    def create_moves(self, moves):
        move_obj = self.env["account.move"].with_context(
            default_journal_id=self.journal_id.id
        )
        move_ids = move_obj.sudo().create(moves)
        for mv in move_ids:
            self.env["syscoon.datev.import.log"].create(
                {
                    "parent_id": self.id,
                    "name": _("Move %s imported", mv["ref"]),
                    "state": "info",
                }
            )
        return move_ids


class ImportDatevLog(models.Model):
    """
    Log line object for import
    """

    _name = "syscoon.datev.import.log"
    _order = "id desc"
    _description = "Datev Import Logs"

    name = fields.Text()
    line = fields.Char()
    parent_id = fields.Many2one("syscoon.datev.import", "Import")
    date = fields.Datetime(
        "Time", readonly=True, default=lambda *a: time.strftime("%Y-%m-%d %H:%M:%S")
    )
    state = fields.Selection(
        [
            ("info", "Info"),
            ("error", "Error"),
            ("standard", "Ok"),
            ("warning", "Warning"),
        ],
        index=True,
        readonly=True,
        default="info",
    )
