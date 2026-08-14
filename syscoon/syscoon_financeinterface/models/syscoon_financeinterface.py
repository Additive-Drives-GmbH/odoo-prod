# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import logging
import re
from contextlib import suppress
from decimal import Decimal
from typing import Union

from lxml import etree, html
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_utils, safe_eval
from odoo.tools.float_utils import float_compare
from pytz import timezone

_logger = logging.getLogger(__name__)


class SyscoonFinanceinterface(models.Model):
    """The class syscoon.financeinterface is the central object to generate
    exports for the selected moves that can be used to be imported in the
    different financial programms on different ways"""

    _name = "syscoon.financeinterface"
    _description = "syscoon Financial Interface"
    _order = "name desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    def _default_mode(self):
        """Function to get the default selected journal ids from the company settings"""
        company_id = self.env.company
        if company_id.export_finance_interface:
            return company_id.export_finance_interface
        return

    def _default_journal(self):
        """Function to get the default selected journal ids from the company settings"""
        return [Command.set(self.env.company.datev_default_journal_ids.ids)]

    name = fields.Char(required=False, readonly=True)
    type = fields.Selection(
        selection=[("date", "Date"), ("date_range", "Date Range")],
        default="date_range",
        required=True,
    )
    # todo: to be removed, replaced by start_date and end_date
    period = fields.Char("Date", required=False, readonly=True)
    is_range_needed = fields.Boolean(compute="_compute_is_range_needed")
    is_type_selction_hidden = fields.Boolean(compute="_compute_is_type_selction_hidden")
    is_journal_needed = fields.Boolean(compute="_compute_is_journal_needed")
    start_date = fields.Date(required=True)
    end_date = fields.Date()
    account_moves_ids = fields.One2many(
        comodel_name="account.move", inverse_name="export_id", readonly=True
    )
    account_moves_count = fields.Integer(
        compute="_compute_account_moves_count", string="No: of Exported Records"
    )
    mode = fields.Selection(
        # TODO: to keep only the none mode for the future
        selection=[
            ("none", "None"),
            ("datev_ascii", "DATEV ASCII"),
            ("datev_ascii_accounts", "DATEV ASCII Accounts"),
            ("datev_xml", "DATEV XML"),
        ],
        required=True,
        default=_default_mode,
    )
    log = fields.Text()
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    journal_ids = fields.Many2many(
        comodel_name="account.journal", string="Journals", default=_default_journal
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("export", "Exported"),
            ("error", "Error"),
        ],
        default="draft",
        readonly=True,
        required=True,
        tracking=True,
    )

    # Item-based processing fields
    item_ids = fields.One2many(
        "syscoon.financeinterface.item", "export_id", "Export Items"
    )
    is_batch_supported = fields.Boolean(
        "Batch Processing Supported",
        compute="_compute_is_batch_supported",
        help="Whether the current mode supports item-based batch processing.",
    )
    auto_process = fields.Boolean(
        "Auto-Process",
        default=True,
        help="If enabled, items are processed automatically by a background job. "
        "If disabled, you must click 'Process Items' to start processing manually.",
    )
    batch_limit = fields.Integer(
        "Process Limit",
        default=50,
        help="Number of items to process at a time (both cron and manual). "
        "Set to 0 to process all items at once.",
    )
    items_limit = fields.Integer(
        "Search Limit",
        default=-1,
        help="Maximum number of invoices fetched when starting an export. "
        "Set to -1 for no limit. Use a positive value to limit memory usage.",
    )

    # Statistics computed from items
    total_items = fields.Integer(
        "Total Items", compute="_compute_item_statistics", store=True
    )
    completed_items = fields.Integer(
        "Completed Items", compute="_compute_item_statistics", store=True
    )
    failed_items = fields.Integer(
        "Failed Items", compute="_compute_item_statistics", store=True
    )
    pending_items = fields.Integer(
        "Pending Items", compute="_compute_item_statistics", store=True
    )
    progress = fields.Float("Progress", compute="_compute_item_statistics", store=True)

    @api.depends("account_moves_ids")
    def _compute_account_moves_count(self):
        for rec in self:
            rec.account_moves_count = len(rec.account_moves_ids)

    @api.depends("item_ids.state")
    def _compute_item_statistics(self):
        """Compute statistics from item states."""
        for record in self:
            items = record.item_ids
            record.total_items = len(items)
            record.completed_items = len(items.filtered(lambda i: i.state == "completed"))
            record.failed_items = len(items.filtered(lambda i: i.state == "failed"))
            record.pending_items = len(items.filtered(lambda i: i.state == "pending"))
            if record.total_items > 0:
                record.progress = (record.completed_items / record.total_items) * 100
            else:
                record.progress = 0

    @api.constrains("start_date", "end_date", "mode")
    def _check_dates(self):
        """Check if the start date is smaller than the end date"""
        for rec in self:
            if rec.end_date and rec.start_date > rec.end_date:
                raise UserError(_("The start date must be smaller than the end date!"))
            if rec.is_range_needed and (not rec.start_date or not rec.end_date):
                mode = rec.mode.replace("_", " ").upper()
                raise UserError(_("Mode %s is require a 'Date Range' to export!", mode))

    @api.depends("mode")
    def _compute_is_batch_supported(self):
        """Compute whether the current mode supports batch processing."""
        for rec in self:
            rec.is_batch_supported = rec._supports_batch_processing()

    def _supports_batch_processing(self):
        """Check if the current mode supports batch processing.

        Override in mode-specific modules to return True if supported.
        Base implementation returns False.
        """
        return False

    @api.depends("mode")
    def _compute_is_range_needed(self):
        for rec in self:
            rec.is_range_needed = rec.mode in self._period_required_by_mode()

    @api.depends("mode")
    def _compute_is_type_selction_hidden(self):
        for rec in self:
            rec.is_type_selction_hidden = rec.mode in self._type_selection_hide_modes()

    @api.depends("mode")
    def _compute_is_journal_needed(self):
        for rec in self:
            rec.is_journal_needed = rec.mode in self._journal_required_by_mode()

    @api.onchange("mode")
    def _onchange_mode(self):
        self.type = (
            "date_range" if self.mode in self._period_required_by_mode() else "date"
        )
        self.journal_ids = [Command.set(self.env.company.datev_default_journal_ids.ids)]

    def _period_required_by_mode(self):
        return []

    def _type_selection_hide_modes(self):
        return []

    def _journal_required_by_mode(self):
        return []

    @api.depends("name", "start_date", "end_date")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name or _('Export')} ({rec._period()})"

    def _period(self):
        if self.start_date and self.end_date:
            return (
                fields.Date.to_string(self.start_date)
                + " - "
                + fields.Date.to_string(self.end_date)
            )
        if self.start_date and not self.end_date:
            return fields.Date.to_string(self.start_date)
        return ""

    def _float_to_char(self, key, val):
        """Converts all floats of a line to char for using in DATEV ASCII Export"""
        if not val and key == "Basis-Umsatz":
            val = ""
        if self._is_float_string(val) and key != "Kurs":
            val = str(float_utils.float_repr(float(val), 2)).replace(".", ",")
        if self._is_float_string(val) and key == "Kurs":
            val = str(float_utils.float_repr(float(val), 4)).replace(".", ",")
        return val

    def _is_float_string(self, val):
        if isinstance(val, Union[int, float]):
            return isinstance(val, float) and val is not int(val)
        try:
            float(val)
            return "." in val
        except (ValueError, TypeError):
            return False

    def _apply_template_config(self, move, line, data):
        """Converts all floats of a line to char for using in DATEV ASCII Export"""
        template_keys = data.get("template_keys", {})
        for key, val in line.items():
            value = self._apply_template_line_config(move, template_keys, key, val)
            line[key] = self._float_to_char(key, value)
        return line

    def _apply_template_line_config(self, move, template_keys, key, value):
        """Applies the regex to the value"""
        values = template_keys.get(key, {})
        value = self._apply_value_code_config(move, values.get("force_value"), key, value)
        return self._apply_regex_config(values.get("expression"), key, value)

    def _apply_value_code_config(self, move, key_code, key, value):
        if not key_code or not isinstance(value, str):
            return value
        eval_context = self._get_eval_context(move, value)
        # nocopy allows to return 'action'
        safe_eval.safe_eval(key_code.strip(), eval_context, mode="exec", nocopy=True)
        return eval_context.get("value", value)

    def _apply_regex_config(self, key_regex, key, value):
        """Applies the regex to the value"""
        if not key_regex:
            return value
        try:
            # Check if the regex contains capturing groups
            group_count = re.compile(key_regex).groups
            if group_count > 0:
                # Dynamically construct the replacement string to use all groups
                replacement = "".join(rf"\{i}" for i in range(1, group_count + 1))
                return re.sub(rf"{key_regex}", replacement, str(value))
            # No groups, replace the entire match
            return re.sub(rf"{key_regex}", "", str(value))
        except Exception as e:
            _logger.error(_("Financeinterface: %s"), e)
            return value

    def currency_round(self, value, currency=False):
        if not currency:
            currency = self.env.company.currency_id
        return float(
            Decimal(str(currency.round(value) / currency.rounding))
            * Decimal(str(currency.rounding))
        )

    def convert_date(self, date, date_format="%d%m%y"):
        """Converts the date to the needed format for the export:
        The format can be given free by using the known python formats"""
        return date.strftime(date_format)

    def copy(self, default=None):
        """Prevent the copy of the object"""
        if self.env.context.get("prevent_copy", True):
            raise UserError(_("Warning! Exports cannot be duplicated."))
        return super().copy(default=default)

    @api.model_create_multi
    def create(self, vals_list):
        """Method to create the export and set the name"""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "syscoon.financeinterface.name"
                )
        return super().create(vals_list)

    def _get_report_base_filename(self):
        self.ensure_one()
        return self.name

    @api.model
    def text_from_html(
        self, html_content, max_words=None, max_chars=None, ellipsis="…", fail=False
    ):
        try:
            doc = html.fromstring(html_content)
        except (TypeError, etree.XMLSyntaxError, etree.ParserError):
            if fail:
                raise
            _logger.exception("Failure parsing this HTML:\n%s", html_content)
            return ""
        words = "".join(doc.xpath("//text()")).split()
        suffix = max_words and len(words) > max_words
        if max_words:
            words = words[:max_words]
        text = " ".join(words)
        suffix = suffix or max_chars and len(text) > max_chars
        if max_chars:
            text = text[: max_chars - (len(ellipsis) if suffix else 0)].strip()
        if suffix:
            text += ellipsis
        return text

    def action_export(self):
        """Set the export to exported state"""
        if not hasattr(self, f"_export_{self.mode}"):
            raise UserError(
                _(
                    "The export method %s is not implemented. Please implement it in the model!",
                    self.mode,
                )
            )
        return getattr(self, f"_export_{self.mode}")()

    def action_draft(self):
        """Set the export to draft state"""
        if hasattr(self, f"_draft_{self.mode}"):
            getattr(self, f"_draft_{self.mode}")()
        return self.write({"state": "draft"})

    def reset_export(self):
        self.action_draft()
        # Skip export if any warning/exception occurs in action_export
        with suppress(Exception):
            self.action_export()

    def _get_eval_context(self, move, value):
        return {
            "move": move,
            "current_value": value,
            "interface": self,
            "uid": self._uid,
            "user": self.env.user,
            "time": safe_eval.time,
            "datetime": safe_eval.datetime,
            "dateutil": safe_eval.dateutil,
            "timezone": timezone,
            "float_compare": float_compare,
        }

    # =========================================================================
    # Item-based processing methods (generic, override in mode-specific modules)
    # =========================================================================

    def write(self, vals):
        res = super().write(vals)
        # Only trigger processing for modes that support batch processing
        if "auto_process" in vals and vals.get("auto_process"):
            batch_supported = self.filtered(lambda r: r._supports_batch_processing())
            if batch_supported:
                self.env["syscoon.financeinterface.item"]._trigger_processing()
        return res

    def action_process_items(self):
        """Manually process pending items.

        Respects batch_limit setting: processes up to batch_limit items at a time.
        If batch_limit is 0, processes all pending items.
        """
        self.ensure_one()
        self = self.with_company(self.company_id)
        if self.state != "queued":
            raise UserError(_("Can only process items when in 'Queued' state"))

        pending_items = self.item_ids.filtered(lambda x: x.state == "pending")
        if not pending_items:
            raise UserError(_("No pending items to process"))

        # Apply batch_limit (0 means process all)
        if self.batch_limit > 0:
            pending_items = pending_items[: self.batch_limit]

        processed_count = len(pending_items)

        # Process items one by one in the export's company context
        for item in pending_items:
            try:
                item.process_item()
            except Exception as e:
                _logger.error("Error processing item %s: %s", item.id, str(e))
                continue

        # Check final state after processing
        self._update_state_after_processing()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Processing Complete"),
                "message": _(
                    "Processed %(count)d items. Completed: %(completed)d, "
                    "Failed: %(failed)d, Pending: %(pending)d",
                    count=processed_count,
                    completed=self.completed_items,
                    failed=self.failed_items,
                    pending=self.pending_items,
                ),
                "type": "success" if self.failed_items == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def retry_failed_items(self):
        """Reset failed items (kept for compatibility)."""
        return self.reset_items()

    def reset_items(self):
        """Reset failed and processing items back to pending."""
        self.ensure_one()
        target_items = self.item_ids.filtered(
            lambda x: x.state in ["failed", "processing"]
        )
        if not target_items:
            raise UserError(_("No failed or processing items to reset"))

        target_items.write(
            {
                "state": "pending",
                "result": False,
                "attachment_ids": [Command.clear()],
            }
        )
        self.write({"state": "queued"})

        # Only trigger auto-processing for modes that support batch processing
        if self.auto_process and self._supports_batch_processing():
            self.env["syscoon.financeinterface.item"]._trigger_processing()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reset Complete"),
                "message": _(
                    "Reset %(count)d item(s) to pending. You can process them again.",
                    count=len(target_items),
                ),
                "type": "info",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_retry_failed_items(self):
        """Retry all failed items immediately.

        Processes each failed item and regenerates the final export ZIP.
        The log is updated to reflect current failed items after retry.
        """
        self.ensure_one()
        failed_items = self.item_ids.filtered(lambda x: x.state == "failed")
        if not failed_items:
            raise UserError(_("No failed items to retry"))

        retry_count = len(failed_items)

        # Process each failed item
        for item in failed_items:
            item.action_retry()

        # Count results after retry
        still_failed = len(self.item_ids.filtered(lambda x: x.state == "failed"))
        now_completed = retry_count - still_failed

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Retry Complete"),
                "message": _(
                    "Retried %(count)d item(s). Success: %(success)d, Still Failed: %(failed)d",
                    count=retry_count,
                    success=now_completed,
                    failed=still_failed,
                ),
                "type": "success" if still_failed == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def cancel_batch(self):
        """Cancel all pending items in the batch."""
        self.ensure_one()
        pending_items = self.item_ids.filtered(lambda x: x.state == "pending")
        pending_items.write({"state": "cancelled"})
        self._update_state_after_processing()

    def _update_state_after_processing(self):
        """Update the export state based on item results.

        State logic:
        - If pending items remain: stay in 'queued'
        - If completed items exist: let _finalize_export() set 'export' state
          (even if some items failed - partial success is still a success)
        - If ALL items failed (no completed): set 'error' state

        Override in mode-specific modules if different logic is needed.
        """
        if self.pending_items > 0:
            # Still have pending items, stay in queued
            return

        if self.completed_items > 0:
            # We have successful items - let _finalize_export() handle state
            # The failed_items field will indicate partial failures
            return

        # Only set error if ALL items failed (no completed items)
        if self.failed_items > 0:
            self.write({"state": "error"})
