# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import base64
import gc
import logging
import os
import re
import shutil
import tempfile
import zipfile
from collections import namedtuple
from functools import partial
from itertools import chain

from lxml import etree
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import pdf

_logger = logging.getLogger(__name__)

# Module constants
CLEAN_NUMBER_PATTERN = re.compile(r"\w+")  # Pattern for cleaning invoice numbers


class SyscoonFinanceinterface(models.Model):
    """Inherits the basic class to provide the export for DATEV ASCII"""

    _inherit = "syscoon.financeinterface"

    mode = fields.Selection(
        selection_add=[("datev_xml", "DATEV XML")],
        ondelete={"datev_xml": lambda recs: recs.write({"mode": "none"})},
    )
    xml_mode = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("extended", "Extended"),
            ("bedi", "BEDI Link"),
            ("x-rechnungen", "X-Rechnungen (ohne ZuGferd)"),
        ],
        string="XML-Export Methode",
        help="Export Methode: Standard: without Accounts, Extended: with Accounts",
    )
    xml_invoices = fields.Selection(
        [
            ("customers", "Customer Invoices"),
            ("vendors", "Vendor Bills"),
            ("both", "Both"),
        ],
        string="Invoices",
    )
    exclude_bedi_exported = fields.Boolean(
        string="Exclude BEDI", help="Exclude already exported BEDI invoices"
    )
    bedi_moves_ids = fields.One2many(
        "account.move", "datev_bedi_export_id", readonly=True
    )
    bedi_move_count = fields.Integer(
        "BEDI Move Count", compute="_compute_bedi_move_count"
    )
    move_count = fields.Integer("Total Moves", compute="_compute_move_count", store=True)
    working_zip_path = fields.Char(
        "Working ZIP Path",
        readonly=True,
        help="Path to the incremental ZIP file being built during batch processing.",
    )
    working_zip_size = fields.Char(
        "Working ZIP Size",
        compute="_compute_working_zip_size",
        help="Current size of the working ZIP file being built.",
    )

    @api.depends("working_zip_path")
    def _compute_working_zip_size(self):
        for record in self:
            if record.working_zip_path and os.path.exists(record.working_zip_path):
                size_bytes = os.path.getsize(record.working_zip_path)
                # Format as human-readable size
                if size_bytes < 1024:
                    record.working_zip_size = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    record.working_zip_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    record.working_zip_size = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                record.working_zip_size = False

    @api.depends("bedi_moves_ids")
    def _compute_bedi_move_count(self):
        for record in self:
            record.bedi_move_count = len(record.bedi_moves_ids)

    @api.depends(
        "start_date",
        "end_date",
        "xml_invoices",
        "xml_mode",
        "exclude_bedi_exported",
        "state",
        "items_limit",
    )
    def _compute_move_count(self):
        for record in self:
            if record.state != "draft":
                continue

            if record.mode == "datev_xml" and record.start_date and record.end_date:
                move_domain = record._get_move_domain()
                if move_domain:
                    limit = (
                        record.items_limit
                        if record.items_limit and record.items_limit > 0
                        else None
                    )
                    record.move_count = self.env["account.move"].search_count(
                        move_domain, limit=limit
                    )
                else:
                    record.move_count = 0
            else:
                record.move_count = 0

    def _period_required_by_mode(self):
        return super()._period_required_by_mode() + ["datev_xml"]

    def _type_selection_hide_modes(self):
        return super()._type_selection_hide_modes() + ["datev_xml"]

    def _supports_batch_processing(self):
        """DATEV XML mode supports batch processing."""
        if self.mode == "datev_xml":
            return True
        return super()._supports_batch_processing()

    @api.onchange("xml_mode")
    def _onchange_xml_mode(self):
        """Force vendors when x-rechnungen is selected"""
        if self.mode == "datev_xml" and self.xml_mode == "x-rechnungen":
            self.xml_invoices = "vendors"

    @api.onchange("mode")
    def _onchange_mode(self):
        """Inherits the basic onchange mode"""
        super()._onchange_mode()
        if self.mode != "datev_xml":
            return
        company_id = self.env.company
        self.xml_mode = company_id.export_xml_mode
        self.xml_invoices = "both"

    def _prepare_invoice_pdfs(self, vals):
        """
        @nested - prepare invoice pdf list
        """
        inv_pdfs = []
        new_moves = vals["moves_ok"]
        new_xmls = []
        for i, move in enumerate(vals["moves_ok"]):
            invoice_pdf, errors = self.get_invoice_pdf(move)
            if invoice_pdf:
                inv_pdfs.append(invoice_pdf)
                new_xmls.append(vals["move_xmls"][i])
            if errors:
                new_moves -= move
                vals["error_str"] += f"\n{errors}"
        vals["error_str"] += "\n"
        vals["moves_ok"] = new_moves
        vals["move_xmls"] = new_xmls
        return inv_pdfs

    def _export_datev_xml(self):
        """Method that generates the export by the given parameters.

        Always uses item-based processing for consistency and visibility.
        The auto_process flag only controls whether items are processed
        automatically via cron or manually by the user.
        """
        return self._export_datev_xml_batch()

    def action_export(self):
        """Export button handler adapted to batch processing state."""
        self.ensure_one()
        if self.mode != "datev_xml":
            return super().action_export()

        # If already queued, either continue processing or finalize
        if self.state == "queued":
            pending_or_processing = self.item_ids.filtered(
                lambda x: x.state in ["pending", "processing"]
            )
            if pending_or_processing:
                return self.action_process_items()
            # No pending/processing items: finalize/export result
            return self._finalize_export()

        return super().action_export()

    def _export_datev_xml_batch(self):
        """Start item-based export processing.

        Creates one item per invoice and sets state to 'queued'.
        If auto_process is True, triggers the cron job automatically.
        If auto_process is False, user must click 'Process Items' manually.
        """
        total_count = self.move_count
        if total_count == 0:
            date_info = f"{self.start_date}"
            if self.end_date and self.end_date != self.start_date:
                date_info = f"{self.start_date} to {self.end_date}"
            invoice_type = dict(self._fields["xml_invoices"].selection).get(
                self.xml_invoices, "all"
            )
            raise UserError(
                _(
                    "No invoices found to export.\n"
                    "Date range: %(date)s\n"
                    "Invoice type: %(type)s\n"
                    "Please verify your filters and ensure posted invoices exist.",
                    date=date_info,
                    type=invoice_type,
                )
            )
        return self.start_batch_processing()

    def _export_datev_xml_sync(self):
        """Original synchronous export method for smaller datasets (deprecated)"""

        def clean_move_number(move):
            """
            Return a cleaned invoice
            number consisting only of
            alphanumeric characters
            """
            return "".join(re.findall(r"\w+", move.name or ""))

        invoice_mode = self.xml_mode
        invoice_selection = self.xml_invoices
        exclude_bedi_exported = self.exclude_bedi_exported
        invoice_type = []
        self.write(
            {
                "xml_mode": invoice_mode,
            }
        )
        if invoice_selection in ["customers", "both"]:
            invoice_type.extend(["out_invoice", "out_refund"])
        if invoice_selection in ["vendors", "both"]:
            invoice_type.extend(["in_invoice", "in_refund"])
        move_domain = [
            ("date", ">=", self.start_date),
            ("date", "<=", self.end_date),
            ("move_type", "in", invoice_type),
            ("state", "=", "posted"),
        ]
        if invoice_mode != "bedi":
            move_domain.append(("export_id", "=", False))
        if exclude_bedi_exported:
            move_domain.append(("datev_bedi_export_id", "=", False))
        moves = self.env["account.move"].search(move_domain)
        if not moves:
            raise UserError(
                _("There are no invoices to export in the selected date range!")
            )
        vals = self.generate_export_invoices(invoice_mode, moves)
        with tempfile.TemporaryDirectory() as export_path:
            invoice_pdfs = self._prepare_invoice_pdfs(vals)
            move_numbers = vals["moves_ok"].mapped(clean_move_number)
            invoice_docs = zip(
                vals["moves_ok"], move_numbers, vals["move_xmls"], invoice_pdfs
            )
            docs = map(partial(self.write_export_invoice, export_path), invoice_docs)
            doc_paths, doc_errors = self.write_docs(docs, export_path, invoice_mode)
            if doc_errors:
                vals["error_str"] += "\n".join(doc_errors)
                vals["error_str"] += "\n"
            if doc_paths and vals["moves_ok"]:
                zip_file = self.make_zip_file(export_path, doc_paths, invoice_mode)
                if not zip_file:
                    vals["error_str"] += _(
                        "No ZIP file could be created. Please check the logs."
                    )
                    return
                self.env["ir.attachment"].create(
                    {
                        "name": f"{self.name}.zip",
                        "store_fname": f"{self.name}.zip",
                        "res_model": "syscoon.financeinterface",
                        "res_id": self.id,
                        "type": "binary",
                        "datas": base64.b64encode(zip_file),
                    }
                )
        self._link_datev_xml_accounts_move(invoice_mode, vals)
        return True

    def _draft_datev_xml(self):
        self._cleanup_working_zip()
        self.env["ir.attachment"].search(
            [
                ("res_id", "=", self.id),
                ("res_model", "=", self._name),
                ("name", "=", f"{self.name}.zip"),
            ]
        ).unlink()
        self.item_ids.unlink()
        ctx = {"skip_invoice_sync": True, "skip_invoice_line_sync": True}
        return self.with_context(**ctx).write(
            {
                "log": "",
                "account_moves_ids": [Command.clear()],
                "bedi_moves_ids": [Command.clear()],
            }
        )

    def _link_datev_xml_accounts_move(self, invoice_mode, vals):
        ctx = {"skip_invoice_sync": True, "skip_invoice_line_sync": True}
        if invoice_mode == "bedi":
            vals["moves_ok"].with_context(**ctx).write({"datev_bedi_export_id": self.id})
        else:
            vals["moves_ok"].with_context(**ctx).write({"export_id": self.id})
            if vals["move_errors"]:
                errors = self.env["account.move"].browse(vals["move_errors"])
                vals["move_errors"] = errors
                vals["move_errors"].with_context(**ctx).write({"export_id": False})
        # Non-blocking notes (e.g. city truncated to 30 chars for the XML)
        log_messages = self._get_city_length_warnings(vals["moves_ok"])
        if vals["error_str"]:
            log_messages = [vals["error_str"]] + log_messages
        if log_messages:
            self.write({"log": "\n".join(log_messages)})

    def _get_city_length_warnings(self, moves):
        """Return non-blocking log notes for partners whose city exceeds the
        DATEV city limit of 36 characters.

        The city is truncated to 36 characters in the XML (see
        ``account.move._prepare_datev_xml_address_values``) so the export is
        not blocked. This note informs the user that a truncation happened.

        Partners are de-duplicated so each affected partner is reported once,
        regardless of how many moves reference it (e.g. the company partner,
        which appears on every move).
        """
        max_length = 36
        partners = moves.mapped("commercial_partner_id") | moves.mapped(
            "company_id.partner_id"
        )
        warnings = []
        for partner in partners:
            if partner.city and len(partner.city) > max_length:
                warnings.append(
                    _(
                        'The city "%(city)s" of partner %(partner)s exceeds '
                        '%(max)s characters and was truncated to "%(truncated)s" '
                        "in the DATEV XML export.",
                        city=partner.city,
                        partner=partner.name,
                        max=max_length,
                        truncated=partner.city[:max_length],
                    )
                )
        return warnings

    def _get_missing_fields(self, partner, required_fields):
        return [
            _(
                "The partner %(name)s has no %(label)s.",
                name=partner.name,
                label=partner._fields[field].string,
            )
            for field in required_fields
            if field in partner._fields and not partner[field]
        ]

    def _check_partner_data(self, move):
        """Check if the partner's address and account data are complete."""
        param_config_obj = self.env["ir.config_parameter"].sudo()

        # Read config parameters and parse comma-separated values
        address_fields = param_config_obj.get_param(
            "partner_check.address_fields", "street,zip,city"
        ).split(",")
        out_fields = param_config_obj.get_param(
            "partner_check.account_fields.out", "debitor_number"
        ).split(",")
        in_fields = param_config_obj.get_param(
            "partner_check.account_fields.in", "creditor_number"
        ).split(",")

        # Choose the right account fields
        account_fields = []
        if move.move_type in ["out_invoice", "out_refund"]:
            account_fields = out_fields
        elif move.move_type in ["in_invoice", "in_refund"]:
            account_fields = in_fields

        # Sanitize whitespace
        address_fields = [f.strip() for f in address_fields if f.strip()]
        account_fields = [f.strip() for f in account_fields if f.strip()]
        account_partner = move.commercial_partner_id
        errors = self._get_missing_fields(
            move.partner_id, address_fields
        ) + self._get_missing_fields(account_partner, account_fields)
        if errors:
            errors = [
                _(
                    "%(move)s (id=%(move_id)s) could not be exported:",
                    move=move.name,
                    move_id=move.id,
                )
            ] + errors
        return errors

    def _get_move_xml_attachments(self, move):
        """Collect the XML attachments of a move for the DATEV XML export.

        A bill created from an e-invoice (journal upload, Documents, mail
        alias) stores its XML linked to the ``ubl_cii_xml_file`` binary
        field. Such attachments carry ``res_field`` and are hidden from
        ``move.attachment_ids`` because ``ir.attachment._search`` adds an
        implicit ``res_field = False`` filter. XML files uploaded by
        non-system users are stored with mimetype ``text/plain``
        (``ir.attachment._check_contents``), so the file extension is
        checked in addition to the mimetype.
        """
        attachments = move.attachment_ids | self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("res_field", "=", "ubl_cii_xml_file"),
            ]
        )
        return attachments.filtered(
            lambda a: a.mimetype in ("application/xml", "text/xml")
            or (a.name or "").lower().endswith(".xml")
        )

    def _get_existing_xml(self, move, invoice_mode):
        if invoice_mode != "x-rechnungen":
            return self._get_move_xml_attachments(move)
        return False

    def generate_export_invoices(self, invoice_mode, moves):  # noqa: C901
        """Generates a list of dicts which have all the export lines to DATEV"""
        error_str = ""
        move_xmls = []
        move_errors = []
        moves_with_xml = []
        moves_stat = {"success": self.env["account.move"], "failed": []}

        for move in moves:
            try:
                error_list = []

                xml_attachments = self._get_move_xml_attachments(move)
                pdf_attachments = move.attachment_ids.filtered(
                    lambda a: a.mimetype == "application/pdf"
                )

                if invoice_mode == "x-rechnungen":
                    # Only export vendor bills
                    if move.move_type not in ["in_invoice", "in_refund"]:
                        move_errors.append(move.id)
                        error_str += _(
                            "%(name)s (id=%(move_id)s) skipped: Only vendor bills "
                            "allowed in X-Rechnungen export.\n",
                            name=move.name,
                            move_id=move.id,
                        )
                        continue

                    # X-Rechnungen only exports XML, check XML attachments first
                    if xml_attachments:
                        xml = xml_attachments[0].raw
                    else:
                        move_errors.append(move.id)
                        error_str += _(
                            "%(name)s (id=%(move_id)s) skipped: "
                            "No XML attachment found for X-Rechnungen export.\n",
                            name=move.name,
                            move_id=move.id,
                        )
                        continue

                else:
                    # Standard / Extended / BEDI
                    # Vendor bill with XML only, treat as X-Rechnung so skip
                    if (
                        move.move_type in ["in_invoice", "in_refund"]
                        and xml_attachments
                        and not pdf_attachments
                    ):
                        move_errors.append(move.id)
                        error_str += _(
                            "%(name)s (id=%(move_id)s) skipped: Has only XML, treated as X-Rechnung."
                            " Use X-Rechnungen export.\n",
                            name=move.name,
                            move_id=move.id,
                        )
                        continue

                    # If both PDF and XML are attached,ignore XML, generate XML from move
                    # Proceed normally to generate XML (skip for BEDI mode)
                    if invoice_mode == "bedi":
                        xml = b""  # Empty bytes for BEDI mode - no invoice XML needed
                        error_list = []
                    else:
                        xml, error_list = self.get_invoice_xml(move, invoice_mode)

                if not error_list:
                    move_xmls.append(xml)
                    moves_with_xml.append(move.id)
                else:
                    move_errors.append(move.id)
                    error_str += "\n".join(error_list) + "\n"

                moves_stat["success"] += move

            except Exception as e:
                moves_stat["failed"].append({"move": move.name, "error": str(e)})

        if moves_stat["failed"]:
            error_text = "\n\n".join(
                [f'{stat["move"]}\n\n{stat["error"]}' for stat in moves_stat["failed"]]
            )
            error_text = [
                "Execution failed! The XML file is preventing the following",
                f"moves from proceeding.\n{error_text}",
            ]
            raise ValidationError(_(" ".join(error_text)))

        moves_ok = self.env["account.move"].browse(moves_with_xml)
        return {
            "move_errors": move_errors,
            "error_str": error_str,
            "move_xmls": move_xmls,
            "moves_ok": moves_ok,
        }

    def get_invoice_pdf(self, moves):
        """Return the PDF report for a given invoice.

        If no PDF exists, generates one using account.move.send which
        properly embeds factur-x.xml via account_edi_ubl_cii hooks.
        """
        report = namedtuple("Report", ["content", "filetype"])
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "in", moves.ids),
                ("mimetype", "=", "application/pdf"),
                "|",
                ("res_field", "!=", False),
                ("res_field", "=", False),
            ],
            order="id asc",
        )
        pdf_datas = self._get_pdf_data(attachments)
        res_ids = attachments.mapped("res_id")

        # Generate PDF for moves without existing attachment
        if no_attachment_moves := moves.filtered(lambda m: m.id not in res_ids):
            # Use account.move.send to generate PDF with embedded factur-x.xml
            generated_pdfs = self._generate_pdf_with_embedded_xml(no_attachment_moves)
            pdf_datas.extend(generated_pdfs)

        try:
            # CRITICAL: Skip merge for single PDF to preserve embedded factur-x.xml
            # pdf.merge_pdf() strips embedded file attachments like factur-x.xml
            merged_content = (
                pdf_datas[0] if len(pdf_datas) == 1 else pdf.merge_pdf(pdf_datas)
            )
            report_make = report._make((merged_content, "pdf"))
            errors = False
        except Exception as e:
            report_make = False
            move_name = moves[0].name if moves else "Unknown"
            move_id = moves[0].id if moves else "N/A"
            errors = _(
                "The PDF attached to invoice %(name)s appears to be corrupted.(id=%(id)s)\n"
                "ERROR details: \n"
                "%(error)s\n",
                name=move_name,
                id=move_id,
                error=e,
            )
        return report_make, errors

    def _generate_pdf_with_embedded_xml(self, moves):
        """Generate PDFs with embedded factur-x.xml using Odoo's mechanism.

        Uses account.move.send._generate_invoice_documents() which triggers
        the account_edi_ubl_cii hooks to embed factur-x.xml into the PDF.

        Falls back to plain PDF generation if account_edi_ubl_cii is not installed.
        """
        pdf_contents = []
        move_send = self.env["account.move.send"]

        for move in moves:
            # Prepare invoice data with default settings
            invoice_data = move_send._get_default_sending_settings(move)
            invoice_data["pdf_report"] = move_send._get_default_pdf_report_id(move)

            invoices_data = {move: invoice_data}

            # Generate invoice documents
            # If account_edi_ubl_cii is installed, factur-x.xml will be embedded
            # If not, we get a plain PDF using Odoo's standard flow
            try:
                move_send._generate_invoice_documents(invoices_data)
            except Exception as e:
                # Log error and fall back to plain PDF
                error_msg = _(
                    "Factur-X XML generation failed for %(name)s (id=%(id)s): "
                    "%(error)s\nContinuing with plain PDF only.",
                    name=move.name,
                    id=move.id,
                    error=str(e),
                )
                _logger.warning(error_msg)
                # Append to export log field
                current_log = self.log or ""
                self.log = current_log + error_msg + "\n"

            # Extract the generated PDF content
            if invoice_data.get("pdf_attachment_values"):
                pdf_contents.append(invoice_data["pdf_attachment_values"]["raw"])
            elif move.invoice_pdf_report_id:
                pdf_contents.append(base64.b64decode(move.invoice_pdf_report_id.datas))
            else:
                # Fallback: generate plain PDF using the report from invoice_data
                pdf_report = invoice_data["pdf_report"]
                result, _report_type = (
                    self.env["ir.actions.report"]
                    .with_company(move.company_id)
                    ._pre_render_qweb_pdf(pdf_report.report_name, res_ids=[move.id])
                )
                # Extract PDF content from the OrderedDict structure
                # _pre_render_qweb_pdf returns: OrderedDict({move_id: {'stream': BytesIO}})
                if result and move.id in result:
                    pdf_stream = result[move.id].get("stream")
                    if pdf_stream:
                        pdf_contents.append(pdf_stream.getvalue())

        return pdf_contents

    def _get_pdf_data(self, attachments):
        return [base64.decodebytes(attachment.datas) for attachment in attachments]

    def get_invoice_xml(self, move_id, invoice_mode):
        """Return the XML Export for a given invoice"""
        if errors := self._check_partner_data(move_id):
            return "", errors
        schema = etree.parse(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "schemas/Belegverwaltung_online_invoice_v050.xsd",
            )
        )
        schema = etree.XMLSchema(schema)
        parser = etree.XMLParser(schema=schema, encoding="utf-8")
        xml = self.env["syscoon.financeinterface.xml"].create_invoice_xml(
            move_id, invoice_mode
        )
        try:
            etree.fromstring(xml, parser)
        except (etree.XMLSyntaxError, ValueError) as e:
            errors = [self.get_error_msg(move_id)]
            for arg in e.args:
                errors.append(arg)
            # Add helpful hint based on error
            hint = self._get_error_hint(move_id, str(e))
            if hint:
                errors.append(hint)
            return "", errors
        return xml, []

    def _get_error_hint(self, move, error_msg):
        """Provide user-friendly hints for common XML validation errors.

        Analyzes the error message and invoice data to give actionable advice.
        """
        hints = []

        # Check for missing invoice_item_list (total_amount appears before expected)
        if "invoice_item_list" in error_msg or "total_amount" in error_msg:
            # Check if invoice has zero amount or no valid lines
            valid_lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type not in ["line_section", "line_note"]
                and l.price_subtotal != 0.0
            )
            if not valid_lines:
                hints.append(
                    _(
                        "Hint: Invoice has no exportable line items. "
                        "All lines either have zero amount, are section headers, or notes. "
                        "DATEV XML requires at least one line with a non-zero amount."
                    )
                )
            if move.amount_total == 0:
                hints.append(
                    _("Hint: Invoice total amount is 0. Check if the lines are correct.")
                )

        # Check for missing required fields
        if "required" in error_msg.lower():
            hints.append(
                _(
                    "Hint: Some required XML elements are missing. "
                    "Check invoice and partner data completeness."
                )
            )

        return "\n".join(hints) if hints else ""

    def write_export_invoice(self, dir_path, inv_doc):
        """
        Either both files are written or neither.
        For BEDI mode, only PDF is written (xml will be empty).
        """
        inv_id, name, xml, report = inv_doc

        try:
            # Only write XML if it's not empty (BEDI mode uses empty xml)
            xml_path = None
            if xml:
                xml_path = os.path.join(dir_path, name + ".xml")
                if isinstance(xml, str):
                    with open(xml_path, "w", encoding="utf-8") as file:
                        file.write(xml)
                else:
                    with open(xml_path, "wb") as file:
                        file.write(xml)

            pdf_path = os.path.join(dir_path, ".".join([name, report.filetype]))
            with open(pdf_path, "wb") as file:
                file.write(report.content)
            return (inv_id, name, xml_path, pdf_path)
        except Exception:
            _logger.error(
                _(
                    "An error occurred while saving %(name)s export in %(dir_path)s",
                    name=name,
                    dir_path=dir_path,
                )
            )

    def write_export(self, dir_path, inv_doc):
        """
        Either both files are written or neither.
        """
        inv_id, name, xml, report = inv_doc

        xml_path = os.path.join(dir_path, name + ".xml")
        pdf_path = os.path.join(dir_path, ".".join([name, report.filetype]))
        try:
            with open(xml_path, "w") as file:
                xml = xml.decode(encoding="utf-8", errors="strict")
                file.write(xml)
            with open(pdf_path, "wb") as file:
                file.write(report.content)
            return (inv_id, name, xml_path, pdf_path)
        except Exception:
            _logger.error(
                _(
                    "An error occurred while saving %(name)s export in %(dir_path)s",
                    name=name,
                    dir_path=dir_path,
                )
            )

    @api.model
    def write_docs(self, docs, dir_path, invoice_mode):
        """
        Consumes the docs generator and additionally
        writes an xml file with info of the made exports
        """
        WrittenDoc = namedtuple("WrittenDoc", ["inv", "name", "xml_path", "pdf_path"])

        def get_doc_paths(doc):
            # Return PDF path and XML path if it exists (None for BEDI mode)
            xml_full_path = dir_path + "/" + doc.xml_path if doc.xml_path else None
            return (dir_path + "/" + doc.pdf_path, xml_full_path)

        written_docs = []
        errors = []
        xml_path = False
        for move_id, name, xml_path, pdf_path in docs:
            # Handle None xml_path for BEDI mode (no invoice XML generated)
            xp = xml_path.replace(dir_path + "/", "") if xml_path else None
            pp = pdf_path.replace(dir_path + "/", "")
            written_docs.append(WrittenDoc._make((move_id, name, xp, pp)))
            xml, errors = self.get_documents_xml(written_docs, invoice_mode)
            xml_path, file_err = self.write_export_invoice_info(dir_path, xml)
            if file_err:
                errors.append(file_err)
        return (
            filter(
                None,
                chain((xml_path,), *map(get_doc_paths, written_docs)),
            ),
            errors,
        )

    def get_error_msg(self, move_id):
        return _(
            "%(name)s (id=%(move_id)s) could not be exported: ",
            name=move_id.name,
            move_id=move_id.id,
        )

    def make_zip_file(self, export_path, doc_path, invoice_mode):
        timestamp = fields.Datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_path = os.path.join(export_path, timestamp + ".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as file:
            for path in doc_path:
                if invoice_mode == "x-rechnungen":
                    if path.endswith(".xml") and not path.endswith("document.xml"):
                        file.write(path, os.path.basename(path))
                elif invoice_mode == "bedi":
                    if ".xml" not in path or "document.xml" in path:
                        file.write(path, os.path.basename(path))
                else:
                    file.write(path, os.path.basename(path))
        with open(zip_path, "rb") as datas_file:
            datas_content = datas_file.read()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return datas_content

    def get_documents_xml(self, docs, invoice_mode):
        """Return the XML Export for a given invoice"""
        xml_obj = self.env["syscoon.financeinterface.xml"]
        schema = etree.parse(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "schemas/Document_v050.xsd",
            )
        )
        schema = etree.XMLSchema(schema)
        parser = etree.XMLParser(schema=schema, encoding="utf-8")
        xml = xml_obj.create_documents_xml(docs, invoice_mode)
        try:
            etree.fromstring(xml, parser)
        except Exception as e:
            errors = ["documents.xml"]
            for arg in e.args:
                errors.append(arg)
            return "", errors
        return xml, []

    def write_export_invoice_info(self, dir_path, xml):
        xml_path = os.path.join(dir_path, "document.xml")
        try:
            with open(xml_path, "w") as file:
                file.write(xml.decode("utf-8"))
        except Exception as e:
            if os.path.exists(xml_path):
                os.remove(xml_path)
            doc_error = _(
                "Error while export in %(dir_path)s: %(error)s",
                dir_path=dir_path,
                error=e,
            )
            return "", doc_error
        return xml_path, ""

    def start_batch_processing(self):
        """Start the batch processing.

        Creates one item per invoice and sets state to 'queued'.
        If auto_process is True, triggers the cron job for automatic processing.
        If auto_process is False, waits for manual 'Process Items' click.
        """
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft exports can be started"))

        processing_mode = "automatic (cron)" if self.auto_process else "manual"
        self.message_post(
            body=_(
                "Export started - Processing %(count)d invoices\n"
                "Processing mode: %(mode)s",
                count=self.move_count,
                mode=processing_mode,
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        self._create_items()

        self.message_post(
            body=_("Created %(count)d items (one per invoice)", count=len(self.item_ids)),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        self.write({"state": "queued"})

        # Only trigger cron if auto_process is enabled
        if self.auto_process:
            self._trigger_processing()
        else:
            self.message_post(
                body=_("Click 'Process Items' button to start processing"),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

    def _get_move_domain(self):
        """Get the domain for moves to process - shared between compute and create"""
        invoice_type = []
        if self.xml_mode == "x-rechnungen":
            # DV19-00056: X-Rechnungen exports vendor bills only, regardless of
            # the "Invoices" selection (which is locked to vendors in the UI).
            invoice_type = ["in_invoice", "in_refund"]
        else:
            if self.xml_invoices in ["customers", "both"]:
                invoice_type.extend(["out_invoice", "out_refund"])
            if self.xml_invoices in ["vendors", "both"]:
                invoice_type.extend(["in_invoice", "in_refund"])

        if not invoice_type:
            return []

        move_domain = [
            ("date", ">=", self.start_date),
            ("date", "<=", self.end_date),
            ("move_type", "in", invoice_type),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ]

        if self.xml_mode != "bedi":
            move_domain.append(("export_id", "=", False))
        if self.exclude_bedi_exported:
            move_domain.append(("datev_bedi_export_id", "=", False))

        move_domain.extend(self._get_processing_items_exclusion_domain())
        return move_domain

    def _get_processing_items_exclusion_domain(self):
        """Get domain to exclude moves currently being processed in competing exports."""
        if self.xml_mode == "bedi" and not self.exclude_bedi_exported:
            return []

        domain_items = [
            ("state", "in", ["pending", "processing", "completed"]),
            ("export_id.mode", "=", "datev_xml"),
        ]
        # If we are in an existing export context
        if self.id:
            domain_items.append(("export_id", "!=", self.id))

        processing_items = self.env["syscoon.financeinterface.item"].search(domain_items)
        if processing_items:
            return [("id", "not in", processing_items.move_id.ids)]

        return []

    def _create_items(self):
        """Create export items - one item per move"""
        move_domain = self._get_move_domain()
        if not move_domain:
            raise UserError(_("No invoice types selected"))

        limit = self.items_limit if self.items_limit and self.items_limit > 0 else None
        moves = self.env["account.move"].search(move_domain, order="id", limit=limit)

        _logger.info(
            "Export %s: move_count=%s, actual_moves_found=%s",
            self.id,
            self.move_count,
            len(moves),
        )
        if self.move_count != len(moves):
            _logger.warning(
                "Export %s: Move count mismatch! Expected %s, found %s",
                self.id,
                self.move_count,
                len(moves),
            )

        if not moves:
            raise UserError(_("No invoices found to process"))

        # Create one item per move
        items = []
        for sequence, move in enumerate(moves, start=1):
            items.append(
                {
                    "export_id": self.id,
                    "name": f"Item {sequence}",
                    "sequence": sequence,
                    "move_id": move.id,
                    "state": "pending",
                }
            )

        self.env["syscoon.financeinterface.item"].create(items)

    def _trigger_processing(self):
        """Trigger the cron job to process items"""
        cron = self.env.ref("syscoon_financeinterface.ir_cron_item_processor", False)
        if cron:
            cron._trigger()

    def _get_working_zip_dir(self):
        """Get filestore directory for working ZIPs.

        Uses Odoo's ir.attachment._filestore() for the base path.
        """
        filestore = self.env["ir.attachment"]._filestore()
        working_dir = os.path.join(filestore, "financeinterface_working")
        if not os.path.exists(working_dir):
            os.makedirs(working_dir, exist_ok=True)
        return working_dir

    def _get_working_zip_path(self):
        """Get full path for this export's working ZIP."""
        self.ensure_one()
        return os.path.join(
            self._get_working_zip_dir(), f"export_{self.id}_{self.name}.zip"
        )

    def _init_working_zip(self):
        """Initialize working ZIP if not exists.

        Note: Restoration from final attachment is handled separately by
        _restore_working_zip_from_attachment() which is called during retry.
        """
        self.ensure_one()

        # If working ZIP already exists, return it
        if self.working_zip_path and os.path.exists(self.working_zip_path):
            return self.working_zip_path

        zip_path = self._get_working_zip_path()

        # Create empty ZIP
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED):
            pass

        self.write({"working_zip_path": zip_path})
        return zip_path

    def _append_to_working_zip(self, attachments):
        """Append item attachments to working ZIP.

        Args:
            attachments: ir.attachment recordset to add to the ZIP
        """
        self.ensure_one()
        if not attachments:
            return
        zip_path = self._init_working_zip()
        try:
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
                # Get existing filenames to prevent duplicates
                existing_names = set(zf.namelist())
                for att in attachments:
                    if self._should_skip_file(att.name):
                        continue
                    if att.name in existing_names:
                        _logger.debug("Skipping duplicate file: %s", att.name)
                        continue
                    file_content = base64.b64decode(att.datas)
                    zf.writestr(att.name, file_content)
                    existing_names.add(att.name)
                    del file_content
        except zipfile.BadZipFile:
            _logger.warning("Working ZIP corrupted for export %s, recreating...", self.id)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            self.write({"working_zip_path": False})
            self._append_to_working_zip(attachments)  # Retry
        gc.collect()

    def _append_raw_to_working_zip(self, documents_data):
        """Append raw document bytes directly to working ZIP.

        Args:
            documents_data: List of (filename, raw_bytes) tuples
        """
        self.ensure_one()
        if not documents_data:
            return
        zip_path = self._init_working_zip()
        try:
            with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
                # Get existing filenames to prevent duplicates
                existing_names = set(zf.namelist())
                for filename, content in documents_data:
                    if self._should_skip_file(filename):
                        continue
                    if filename in existing_names:
                        _logger.debug("Skipping duplicate file: %s", filename)
                        continue
                    zf.writestr(filename, content)
                    existing_names.add(filename)
        except zipfile.BadZipFile:
            _logger.warning("Working ZIP corrupted for export %s, recreating...", self.id)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            self.write({"working_zip_path": False})
            self._append_raw_to_working_zip(documents_data)  # Retry

    def _cleanup_working_zip(self):
        """Clean up working ZIP after finalization or reset."""
        self.ensure_one()
        if self.working_zip_path and os.path.exists(self.working_zip_path):
            try:
                os.remove(self.working_zip_path)
                _logger.info("Cleaned up working ZIP: %s", self.working_zip_path)
            except OSError as e:
                _logger.warning(
                    "Failed to clean up working ZIP %s: %s", self.working_zip_path, e
                )
        self.write({"working_zip_path": False})

    def _restore_working_zip_from_attachment(self):
        """Restore working ZIP from final attachment before it's deleted.

        Called during retry to preserve existing files.
        Must be called BEFORE the final attachment is deleted.
        Removes document.xml so it can be regenerated during finalization.
        """
        self.ensure_one()

        # Skip if working ZIP already exists
        if self.working_zip_path and os.path.exists(self.working_zip_path):
            return

        # Find final ZIP attachment
        final_zip_attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=", f"{self.name}.zip"),
            ],
            limit=1,
        )

        if not final_zip_attachment:
            return

        # Restore to working path
        zip_path = self._get_working_zip_path()
        final_zip_content = base64.b64decode(final_zip_attachment.datas)
        with open(zip_path, "wb") as zip_file:
            zip_file.write(final_zip_content)

        # Remove document.xml from the restored ZIP so it will be regenerated
        # during finalization with the updated list of completed items
        self._remove_document_xml_from_working_zip(zip_path)

        self.write({"working_zip_path": zip_path})
        _logger.info("Restored working ZIP from final attachment for export %s", self.id)

    def _remove_document_xml_from_working_zip(self, zip_path):
        """Remove document.xml from working ZIP to allow regeneration.

        Python's zipfile doesn't support deletion, so we recreate the ZIP
        without document.xml.
        """
        if not os.path.exists(zip_path):
            return

        temp_path = zip_path + ".tmp"
        try:
            with zipfile.ZipFile(zip_path, "r") as zin, zipfile.ZipFile(
                temp_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as zout:
                for item in zin.infolist():
                    if item.filename != "document.xml":
                        zout.writestr(item, zin.read(item.filename))
            # Replace original with filtered version
            os.replace(temp_path, zip_path)
            _logger.debug("Removed document.xml from working ZIP for regeneration")
        except Exception as e:
            _logger.warning("Failed to remove document.xml from ZIP: %s", e)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _finalize_export(self):
        """Finalize the export by creating the final ZIP file with document.xml"""
        # Free up memory before heavy operation
        gc.collect()
        try:
            # Do not finalize while items are still processing
            processing_items = self.item_ids.filtered(lambda x: x.state == "processing")
            if processing_items:
                _logger.info(
                    "Postponing finalization for export %s: %d item(s) still processing",
                    self.name,
                    len(processing_items),
                )
                return

            completed_items = self.item_ids.filtered(lambda x: x.state == "completed")

            if not completed_items:
                self._handle_no_completed_items()
                return

            with tempfile.TemporaryDirectory() as temp_dir:
                final_zip_path = self._create_final_zip(temp_dir, completed_items)
                self._save_final_attachment(final_zip_path, len(completed_items))

            self._link_processed_moves()
            self._send_notification()
            self._cleanup_working_zip()

        except Exception as e:
            self._handle_finalize_error(e)

    def _handle_no_completed_items(self):
        """Handle case when no items were successfully processed."""
        error_messages = [_("No items were successfully processed")]
        for item in self.item_ids.filtered(lambda x: x.state == "failed"):
            if item.result:
                error_messages.append(f"{item.move_id.name}: {item.result}")

        self.message_post(
            body=_("Export failed - No items were successfully processed"),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        self.write({"state": "error", "log": "\n".join(error_messages)})

    def _create_final_zip(self, temp_dir, completed_items):
        """Create final ZIP using incremental working ZIP if available."""
        final_zip_path = os.path.join(temp_dir, f"{self.name}.zip")

        if self.working_zip_path and os.path.exists(self.working_zip_path):
            # Use incremental ZIP - just copy and add document.xml
            shutil.copy2(self.working_zip_path, final_zip_path)
            with zipfile.ZipFile(
                final_zip_path, "a", compression=zipfile.ZIP_DEFLATED
            ) as final_zip:
                self._add_document_xml(final_zip, temp_dir, completed_items)
        else:
            # Fallback for backward compatibility (old exports without working ZIP)
            with zipfile.ZipFile(
                final_zip_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as final_zip:
                self._merge_item_attachments(final_zip, completed_items)
                self._add_document_xml(final_zip, temp_dir, completed_items)

        return final_zip_path

    def _merge_item_attachments(self, final_zip, completed_items):
        """Merge all item attachment contents into the final ZIP."""
        for item in completed_items:
            attachments = item.attachment_ids
            if not attachments:
                continue

            for attachment in attachments:
                if self._should_skip_file(attachment.name):
                    continue

                file_content = base64.b64decode(attachment.datas)
                final_zip.writestr(attachment.name, file_content)
                del file_content

        gc.collect()

    def _extract_item_zip(self, temp_dir, item, prefix="item"):
        """Extract an item's ZIP file to temp directory.

        Args:
            temp_dir: Directory to extract to
            item: The item record containing the attachment
            prefix: Prefix for the extracted file name (default: "item")

        Returns:
            Path to the extracted ZIP file
        """
        item_zip_data = base64.b64decode(item.attachment_ids[0].datas)
        item_zip_path = os.path.join(temp_dir, f"{prefix}_{item.sequence}.zip")

        with open(item_zip_path, "wb") as file:
            file.write(item_zip_data)

        return item_zip_path

    def _copy_zip_contents(self, final_zip, item_zip_path):
        """Copy contents from item ZIP to final ZIP, filtering by mode"""
        with zipfile.ZipFile(item_zip_path, "r") as item_zip:
            for file_info in item_zip.infolist():
                # Security: sanitize filename to prevent path traversal attacks
                safe_filename = os.path.basename(file_info.filename)
                if not safe_filename or self._should_skip_file(safe_filename):
                    continue

                file_data = item_zip.read(file_info.filename)
                final_zip.writestr(safe_filename, file_data)

    def _should_skip_file(self, filename):
        """Check if file should be skipped based on export mode"""
        if self.xml_mode == "bedi":
            # BEDI: skip all XML except document.xml
            return filename.endswith(".xml") and not filename.endswith("document.xml")
        if self.xml_mode == "x-rechnungen":
            # DV19-00056: X-Rechnungen exports only XML, skip all PDFs
            return filename.endswith(".pdf")
        # Other modes: don't skip any files
        return False

    def _add_document_xml(self, final_zip, temp_dir, completed_items):
        """Generate and add document.xml to the final ZIP"""
        written_docs = self._collect_written_docs(completed_items)

        if not written_docs:
            return

        xml_content, doc_errors = self.get_documents_xml(written_docs, self.xml_mode)
        if xml_content and not doc_errors:
            final_zip.writestr("document.xml", xml_content)
        elif doc_errors:
            _logger.warning("Document XML errors: %s", doc_errors)

    def _collect_written_docs(self, completed_items):
        """Collect written_doc objects from all completed items"""
        written_doc = namedtuple("written_doc", ["inv", "name", "xml_path", "pdf_path"])
        written_docs = []

        for item in completed_items:
            attachments = item.attachment_ids
            if not attachments:
                continue

            item_docs = self._create_written_docs_from_attachments(
                item, attachments, written_doc
            )
            written_docs.extend(item_docs)

        return written_docs

    def _create_written_docs_from_attachments(self, item, attachments, written_doc):
        """Create written_doc objects from item's attachments."""
        move = item.move_id

        move_files = {}
        for attachment in attachments:
            filename = attachment.name
            if not filename:
                continue

            if filename.endswith(".xml"):
                move_files["xml"] = filename
            elif filename.endswith(".pdf"):
                move_files["pdf"] = filename

        if not move_files:
            return []

        doc = self._create_single_written_doc(move, move_files, written_doc)
        return [doc] if doc else []

    def _extract_item_docs(self, temp_dir, item, written_doc):
        """Extract written_doc objects from a single item"""
        item_zip_path = self._extract_item_zip(temp_dir, item, prefix="temp_item")

        with zipfile.ZipFile(item_zip_path, "r") as item_zip:
            move_files = self._group_files_by_move(item_zip.namelist())
            # Single move per item
            return self._create_written_docs(item.move_id, move_files, written_doc)

    def _group_files_by_move(self, file_names):
        """Group XML and PDF files by move name.

        Security: sanitizes filenames to prevent path traversal.
        """
        move_files = {}

        for filename in file_names:
            # Security: sanitize filename to prevent path traversal
            safe_filename = os.path.basename(filename)
            if not safe_filename:
                continue

            base_name = safe_filename.rsplit(".", 1)[0]
            if base_name not in move_files:
                move_files[base_name] = {}

            if safe_filename.endswith(".xml"):
                move_files[base_name]["xml"] = safe_filename
            elif safe_filename.endswith(".pdf"):
                move_files[base_name]["pdf"] = safe_filename

        return move_files

    def _create_written_docs(self, move, move_files, written_doc):
        """Create written_doc objects for a single move"""
        written_docs = []

        clean_name = "".join(CLEAN_NUMBER_PATTERN.findall(move.name or ""))
        if clean_name not in move_files:
            return written_docs

        file_info = move_files[clean_name]
        doc = self._create_single_written_doc(move, file_info, written_doc)
        if doc:
            written_docs.append(doc)

        return written_docs

    def _create_single_written_doc(self, move, file_info, written_doc):
        """Create a single written_doc object"""
        if self.xml_mode == "bedi" and "pdf" in file_info:
            # BEDI: PDF only, no XML
            return written_doc(
                inv=move, name=move.name, xml_path="", pdf_path=file_info["pdf"]
            )
        if self.xml_mode == "x-rechnungen":
            # DV19-00056: X-Rechnungen uses only XML, no PDF
            if "xml" in file_info:
                return written_doc(
                    inv=move, name=move.name, xml_path=file_info["xml"], pdf_path=""
                )
            return None
        # Standard/Extended: both XML and PDF required
        if (
            self.xml_mode not in ["bedi", "x-rechnungen"]
            and "xml" in file_info
            and "pdf" in file_info
        ):
            return written_doc(
                inv=move,
                name=move.name,
                xml_path=file_info["xml"],
                pdf_path=file_info["pdf"],
            )
        return None

    def _save_final_attachment(self, final_zip_path, completed_count):
        """Create the final attachment and update state."""
        # Remove existing final ZIP attachments to avoid duplicates when retrying
        existing_zips = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=like", f"{self.name}.zip"),
            ]
        )
        if existing_zips:
            existing_zips.unlink()

        _logger.info("Creating final attachment for export: %s", final_zip_path)
        with open(final_zip_path, "rb") as zip_file:
            self.env["ir.attachment"].create(
                {
                    "name": f"{self.name}.zip",
                    "res_model": self._name,
                    "res_id": self.id,
                    "type": "binary",
                    "datas": base64.b64encode(zip_file.read()),
                }
            )
            _logger.info("Final attachment created for export: %s", final_zip_path)
        # Free memory
        gc.collect()
        # Check if there are failed items for notification message
        failed_count = len(self.item_ids.filtered(lambda x: x.state == "failed"))

        if failed_count > 0:
            _logger.warning(
                "Export completed with partial success - Final ZIP file created with "
                "%d processed invoices. %d invoices failed. "
                "Check the Export Items tab for error details.",
                completed_count,
                failed_count,
            )
            self.message_post(
                body=_(
                    "Export completed with partial success - Final ZIP file created with "
                    "%(completed)d processed invoices. %(failed)d invoices failed. "
                    "Check the Export Items tab for error details.",
                    completed=completed_count,
                    failed=failed_count,
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        else:
            _logger.info(
                "Export completed successfully - Final ZIP file created with "
                "%d processed invoices",
                completed_count,
            )
            self.message_post(
                body=_(
                    "Export completed successfully - Final ZIP file created with "
                    "%(completed)d processed invoices",
                    completed=completed_count,
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

        # Always set state to "export" when we have completed items
        # The failed_items field will indicate partial failures via UI warning
        self.write({"state": "export"})

    def _handle_finalize_error(self, error):
        """Handle errors during finalization"""
        _logger.error("Error finalizing export %s: %s", self.id, str(error))

        self.message_post(
            body=f"Export failed with error: {str(error)}",
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        self.write({"state": "error", "log": str(error)})

    def _link_processed_moves(self):
        """Link moves from completed items."""
        completed_items = self.item_ids.filtered(lambda x: x.state == "completed")
        processed_moves = completed_items.mapped("move_id")

        if processed_moves:
            ctx = {"skip_invoice_sync": True, "skip_invoice_line_sync": True}
            if self.xml_mode == "bedi":
                processed_moves.with_context(**ctx).write(
                    {"datev_bedi_export_id": self.id}
                )
            else:
                processed_moves.with_context(**ctx).write({"export_id": self.id})

        # Log errors or clear log if all items succeeded
        error_messages = []
        for item in self.item_ids.filtered(lambda x: x.state == "failed"):
            if item.result:
                error_messages.append(f"{item.move_id.name}: {item.result}")

        # Non-blocking notes (e.g. city truncated to 30 chars for the XML)
        log_messages = error_messages + self._get_city_length_warnings(processed_moves)

        if log_messages:
            self.write({"log": "\n".join(log_messages)})
        elif self.log:
            # Clear log when all items succeed (e.g., after retry)
            self.write({"log": ""})

    def _send_notification(self):
        """Send completion notification"""
        completed_count = len(self.item_ids.filtered(lambda x: x.state == "completed"))
        failed_count = len(self.item_ids.filtered(lambda x: x.state == "failed"))

        body = _(
            "Your DATEV XML export '%(name)s' has been completed. "
            "Processed %(count)d invoices successfully.",
            name=self.name,
            count=completed_count,
        )

        if failed_count > 0:
            body += _(" %(count)d invoices failed.", count=failed_count)

        self.env["mail.message"].create(
            {
                "message_type": "notification",
                "subject": _("DATEV Export Completed"),
                "body": body,
                "partner_ids": [(4, self.env.user.partner_id.id)],
            }
        )
