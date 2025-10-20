# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import base64
import logging
import os
import re
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

    def _period_required_by_mode(self):
        return super()._period_required_by_mode() + ["datev_xml"]

    def _type_selection_hide_modes(self):
        return super()._type_selection_hide_modes() + ["datev_xml"]

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
        """Method that generates the export by the given parameters"""

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
        self.env["ir.attachment"].search(
            [
                ("res_id", "=", self.id),
                ("res_model", "=", self._name),
                ("name", "=", f"{self.name}.zip"),
            ]
        ).unlink()
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
        if vals["error_str"]:
            self.write({"log": vals["error_str"]})

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

    def _get_existing_xml(self, move, invoice_mode):
        if invoice_mode != "x-rechnungen":
            return move.attachment_ids.filtered(lambda a: a.mimetype == "application/xml")
        return False

    def generate_export_invoices(self, invoice_mode, moves):
        """Generates a list of dicts which have all the export lines to DATEV"""
        error_str = ""
        move_xmls = []
        move_errors = []
        moves_with_xml = []
        moves_stat = {"success": self.env["account.move"], "failed": []}

        for move in moves:
            try:
                error_list = []

                attachments = move.attachment_ids
                xml_attachments = attachments.filtered(
                    lambda a: a.mimetype == "application/xml"
                )
                pdf_attachments = attachments.filtered(
                    lambda a: a.mimetype == "application/pdf"
                )

                if invoice_mode == "x-rechnungen":
                    # Only export vendor bills with exactly one XML and no PDF
                    if move.move_type not in ["in_invoice", "in_refund"]:
                        move_errors.append(move.id)
                        error_str += _(
                            "%(name)s (id=%(move_id)s) skipped: Only vendor bills "
                            "allowed in X-Rechnungen export.\n",
                            name=move.name,
                            move_id=move.id,
                        )
                        continue

                    if len(xml_attachments) != 1 or pdf_attachments:
                        move_errors.append(move.id)
                        error_str += _(
                            "%(name)s (id=%(move_id)s) skipped: Must have exactly one XML"
                            " and no PDF attachments for X-Rechnungen.\n",
                            name=move.name,
                            move_id=move.id,
                        )
                        continue

                    xml = xml_attachments[0].raw  # use attached XML

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
                    # Proceed normally to generate XML
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
        """Return the PDF report for a given invoice"""
        content = False
        report_obj = self.env["ir.actions.report"]
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
        pdf_datas = [base64.decodebytes(attachment.datas) for attachment in attachments]
        res_ids = attachments.mapped("res_id")
        if no_attachment_moves := moves.filtered(lambda m: m.id not in res_ids):
            content, _filetype = report_obj._render_qweb_pdf(
                "account.account_invoices", no_attachment_moves.ids
            )
            pdf_datas.append(content)
        try:
            report_make = report._make((pdf.merge_pdf(pdf_datas), "pdf"))
            errors = False
        except Exception as e:
            report_make = False
            errors = _(
                "The PDF attached to invoice %(name)s appears to be corrupted.(id=%(id)s)\n"
                "ERROR details: \n"
                "%(error)s\n",
                name=moves[0].name,
                id=moves[0].id,
                error=e,
            )
        return report_make, errors

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
            return "", errors
        return xml, []

    def write_export_invoice(self, dir_path, inv_doc):
        """
        Either both files are written or neither.
        """
        inv_id, name, xml, report = inv_doc

        try:
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
            return (dir_path + "/" + doc.pdf_path, dir_path + "/" + doc.xml_path)

        written_docs = []
        errors = []
        xml_path = False
        for move_id, name, xml_path, pdf_path in docs:
            xp = xml_path.replace(dir_path + "/", "")
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
