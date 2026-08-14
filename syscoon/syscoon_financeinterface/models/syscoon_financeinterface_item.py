# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command, _, api, fields, models

_logger = logging.getLogger(__name__)


class SyscoonFinanceinterfaceItem(models.Model):
    """Individual export item for processing a single invoice.

    This is a generic item model that can be used by any export mode.
    Mode-specific modules should inherit and override process_item().
    """

    _name = "syscoon.financeinterface.item"
    _description = "Finance Interface Export Item"
    _order = "export_id, sequence"

    _unique_export_move = models.Constraint(
        "UNIQUE(export_id, move_id)",
        "An item already exists for this move in this export",
    )

    name = fields.Char("Item Name", required=True)
    export_id = fields.Many2one(
        "syscoon.financeinterface",
        "Export",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=1, index=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        string="Status",
        required=True,
        index=True,
    )

    move_id = fields.Many2one(
        "account.move", string="Invoice", required=True, ondelete="restrict", index=True
    )
    partner_id = fields.Many2one(
        "res.partner", related="move_id.partner_id", store=True, string="Partner"
    )
    amount_total = fields.Monetary(
        related="move_id.amount_total", string="Amount", store=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="move_id.currency_id", store=True
    )
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Result Files", readonly=True, store=True
    )
    result = fields.Text(readonly=True, help="Result message or error details.")

    # Related fields for UI visibility conditions
    export_auto_process = fields.Boolean(related="export_id.auto_process", readonly=True)
    export_state = fields.Selection(related="export_id.state", readonly=True)

    def process_item(self):
        """Process this export item.

        Override this method in mode-specific modules to implement
        the actual processing logic (e.g., XML generation, PDF creation).

        The base implementation raises NotImplementedError.
        """
        raise NotImplementedError(
            _("Processing method not implemented for this export mode.")
        )

    def _mark_completed(self, attachments=None):
        """Mark item as completed with optional attachments."""
        vals = {"state": "completed"}
        if attachments:
            vals["attachment_ids"] = [Command.set(attachments.ids)]
        self.write(vals)

    def _handle_processing_error(self, error):
        """Handle processing error - mark failed and log."""
        _logger.error("Error processing item %s: %s", self.id, str(error))
        self.write(
            {
                "state": "failed",
                "result": str(error),
            }
        )

    def action_retry(self):
        """Retry failed item processing immediately (manual).

        Resets the item state and processes it right away.
        Only allowed when auto_process is disabled OR export is already exported.
        """
        self = self.with_company(self.export_id.company_id)
        if self.state not in ("failed", "completed"):
            return {"type": "ir.actions.act_window_close"}

        # Block manual retry if auto_process is enabled and not yet exported
        export = self.export_id
        if export.auto_process and export.state != "export":
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Manual Retry Blocked"),
                    "message": _(
                        "Auto-process is enabled. Items will be processed automatically."
                    ),
                    "type": "warning",
                    "sticky": False,
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        self._clear_final_export_attachment()
        self.write(
            {
                "state": "pending",
                "result": False,
                "attachment_ids": [Command.clear()],
            }
        )
        # Process immediately in the export's company context
        try:
            self.process_item()
        except Exception as e:
            _logger.error("Error in manual retry for item %s: %s", self.id, str(e))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Retry Complete"),
                "message": _("Item state: %s", self.state),
                "type": "success" if self.state == "completed" else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_retry_queue(self):
        """Queue failed item for cron-based retry.

        Resets the item state and triggers the cron job.
        """
        if self.state not in ("failed", "completed"):
            return {"type": "ir.actions.act_window_close"}
        self._clear_final_export_attachment()
        self.write(
            {
                "state": "pending",
                "result": False,
                "attachment_ids": [Command.clear()],
            }
        )
        # Trigger cron processing
        self._trigger_processing()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Queued for Retry"),
                "message": _("Item will be processed by cron"),
                "type": "info",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _clear_final_export_attachment(self):
        """Remove existing final ZIP so it can be regenerated.

        First restores working ZIP from final attachment (if method exists),
        then deletes the final attachment.
        """
        export = self.export_id
        if not export:
            return

        # First, restore working ZIP from final attachment (if exists)
        # This must happen BEFORE deleting the attachment
        if hasattr(export, "_restore_working_zip_from_attachment"):
            export._restore_working_zip_from_attachment()

        # Now safe to delete the final attachment
        final_zip = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "syscoon.financeinterface"),
                ("res_id", "=", export.id),
                ("name", "=", f"{export.name}.zip"),
            ]
        )
        if final_zip:
            final_zip.unlink()

        # Ensure export goes back to queued for re-finalization
        export.write({"state": "queued"})

    @api.model
    def _trigger_processing(self):
        """Trigger the finance interface processing cron job."""
        cron = self.env.ref("syscoon_financeinterface.ir_cron_item_processor", False)
        if cron:
            cron._trigger()

    @api.model
    def _cron_process_items(self):
        """Cron job method to process pending items.

        Processes items from exports where auto_process=True.
        Respects batch_limit from each export (0 means process all).
        Self-triggers if more work is pending.
        """
        # Get all companies that have queued exports
        exports_with_pending = self.env["syscoon.financeinterface"].search(
            [
                ("auto_process", "=", True),
                ("state", "=", "queued"),
            ]
        )

        has_more_work = False

        for export in exports_with_pending:
            # Process in the export's company context
            export = export.with_company(export.company_id)
            pending_items = export.item_ids.filtered(lambda x: x.state == "pending")
            if not pending_items:
                continue

            # Apply batch_limit (0 means process all)
            batch_limit = export.batch_limit or 0
            if batch_limit > 0:
                items_to_process = pending_items[:batch_limit]
                if len(pending_items) > batch_limit:
                    has_more_work = True
            else:
                items_to_process = pending_items

            for item in items_to_process:
                try:
                    # Process item in the export's company context
                    item.with_company(export.company_id).process_item()
                except Exception as e:
                    _logger.error("Error in _cron_process_items: %s", str(e))
                    continue

        # Re-trigger if more work is pending
        if has_more_work:
            self._trigger_processing()
