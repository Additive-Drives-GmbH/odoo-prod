# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
import base64
import csv
import logging
from io import StringIO

from dateutil.relativedelta import relativedelta
from odoo import Command, _, fields, models
from odoo.exceptions import UserError
from pytz import timezone

_logger = logging.getLogger(__name__)


class SyscoonFinanceinterface(models.Model):
    """Inherits the basic class to provide the export for DATEV ASCII"""
    _inherit = "syscoon.financeinterface"

    mode = fields.Selection(
        selection_add=[("datev_ascii", "DATEV ASCII")],
        ondelete={"datev_ascii": lambda recs: recs.write({"mode": "none"})},
    )

    def _period_required_by_mode(self):
        return super()._period_required_by_mode() + ["datev_ascii"]

    def _type_selection_hide_modes(self):
        return super()._type_selection_hide_modes() + ["datev_ascii"]

    def _journal_required_by_mode(self):
        return super()._journal_required_by_mode() + ["datev_ascii"]

    def _export_datev_ascii(self):
        """Method that generates the csv export by the given parameters"""
        moves = self.env["account.move"].search(
            [
                ("date", ">=", self.start_date),
                ("date", "<=", self.end_date),
                ("journal_id", "in", self.journal_ids.ids),
                ("export_id", "=", False),
                ("state", "=", "posted"),
                ("company_id.export_finance_interface_active", "!=", False),
            ]
        )
        if not moves:
            raise UserError(
                _(
                    "There are no moves to export in the selected date "
                    "range and journals!"
                )
            )
        data = self.generate_export_moves(moves)
        export_header = self.generate_export_header(
            self.header_template(), self.start_date, self.end_date
        )
        csv_file = self.generate_csv_file(
            self.export_template(), export_header, data["grouped_lines"]
        )
        if not csv_file:
            raise UserError(
                _("Something went wrong, because a export file could not generated!")
            )
        self.env["ir.attachment"].create(
            {
                "name": f"{self.name}.csv",
                "res_model": "syscoon.financeinterface",
                "res_id": self.id,
                "type": "binary",
                "datas": csv_file,
            }
        )
        ctx = {"skip_invoice_sync": True, "skip_invoice_line_sync": True}
        return moves.with_context(**ctx).write({"export_id": self.id})

    def _draft_datev_ascii(self):
        """Method that generates the csv export by the given parameters"""
        self.env["ir.attachment"].search(
            [
                ("res_id", "=", self.id),
                ("res_model", "=", self._name),
                ("name", "=", f"{self.name}.csv"),
            ]
        ).unlink()
        ctx = {"skip_invoice_sync": True, "skip_invoice_line_sync": True}
        return self.with_context(**ctx).write({"account_moves_ids": [Command.clear()]})

    def _export_template(self):
        """Returns the financeinterface template for the export"""
        return self.env.company.financeinterface_template_id or self.env.ref(
            "syscoon_financeinterface.syscoon_financeinterface_main_template"
        )

    def generate_export_moves(self, moves):
        """Generates a list of dicts which have all the exportlines to datev"""
        template = self._export_template()
        data = {
            "interface": self,
            "lines": {},
            "group": False,
            "grouped_lines": [],
            "template": template,
            "template_keys": template._template_vals(line_type="ascii"),
        }
        for move in moves:
            move.generate_export_lines(data)
        return data

    def action_assign_move_datev_values(self):
        """Assigns the datev values to the moves"""
        self.ensure_one()
        self.env["account.move"].search(
            [
                ("date", ">=", self.start_date),
                ("date", "<=", self.end_date),
                ("journal_id", "in", self.journal_ids.ids),
                ("export_id", "=", False),
                ("state", "=", "posted"),
            ]
        )._assign_datev_values()

    def _remove_leading_zero(self, account):
        """Removes leading zeros from account codes"""
        if self.env.company.datev_remove_leading_zeros and account:
            account = account.lstrip("0")
        return account

    def generate_export_header(self, header, date_from, date_to):
        if int(self.env.company.fiscalyear_last_month) == 12:
            fy_start = date_from.strftime("%Y") + f"{1:02d}" + "01"
        else:
            year_from = date_from - relativedelta(months=11)
            fy_start = (
                year_from.strftime("%Y")
                + f"{int(self.env.company.fiscalyear_last_month) + 1:02d}"
                + "01"
            )
        ctx_tz = timezone(self.env.context.get("tz") or self.env.user.tz or "UTC")
        header.update(
            {
                "Versionsnummer": 700,
                "Datenkategorie": 21,
                "Formatname": "Buchungsstapel",
                "Formatversion": 9,
                "Erzeugtam": fields.datetime.now(ctx_tz).strftime("%Y%m%d%H%M%S%f")[:-3],
                "Exportiertvon": self.env.user.partner_id.name,
                "Berater": self.env.company.datev_accountant_number or "10000",
                "Mandant": self.env.company.datev_client_number or "10000",
                "WJBeginn": fy_start,
                "Sachkontenlaenge": self.env.company.datev_account_code_digits,
                "Datumvon": date_from.strftime("%Y%m%d"),
                "Datumbis": date_to.strftime("%Y%m%d"),
                "Bezeichnung": "Odoo-Export Buchungen",
                "Buchungstyp": 1,
                "Festschreibung": int(self.env.company.datev_enable_fixing),
            }
        )
        return header

    def generate_csv_file(self, template, header, lines):
        """Generates the CSV file as in memory with StringIO"""
        buf = StringIO()
        export_csv = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL)
        if header:
            export_csv.writerow(header.values())
        export_csv.writerow(template.keys())
        for line in lines:
            export_csv.writerow(line.values())
        output = base64.b64encode(buf.getvalue().encode("iso-8859-1", "ignore"))
        return output

    def header_template(self):
        """DATEV ASCII Header V700"""
        return {
            "DATEVFormatKZ": "EXTF",
            "Versionsnummer": "",
            "Datenkategorie": "",
            "Formatname": "",
            "Formatversion": "",
            "Erzeugtam": "",
            "Importiert": "",
            "Herkunft": "OE",
            "Exportiertvon": "",
            "Importiertvon": "",
            "Berater": "",
            "Mandant": "",
            "WJBeginn": "",
            "Sachkontenlaenge": "",
            "Datumvon": "",
            "Datumbis": "",
            "Bezeichnung": "",
            "Diktatkuerzel": "",
            "Buchungstyp": "",
            "Rechnungslegungszweck": "",
            "Festschreibung": "",
            "WKZ": "",
            "res1": "",
            "Derivatskennzeichen": "",
            "res2": "",
            "res3": "",
            "SKR": "",
            "Branchenlösungs-Id": "",
            "res4": "",
            "res5": "",
            "Anwendungsinformationen": "",
        }

    def export_template(self):
        """DATEV ASCII Structure V700"""
        return {
            "Umsatz (ohne Soll/Haben-Kz)": 0.0,
            "Soll/Haben-Kennzeichen": "",
            "WKZ Umsatz": "",
            "Kurs": "",
            "Basis-Umsatz": "",
            "WKZ Basis-Umsatz": "",
            "Konto": "",
            "Gegenkonto (ohne BU-Schlüssel)": "",
            "BU-Schlüssel": "",
            "Belegdatum": "",
            "Belegfeld 1": "",
            "Belegfeld 2": "",
            "Skonto": "",
            "Buchungstext": "",
            "Postensperre": "",
            "Diverse Adressnummer": "",
            "Geschäftspartnerbank": "",
            "Sachverhalt": "",
            "Zinssperre": "",
            "Beleglink": "",
            "Beleginfo - Art 1": "",
            "Beleginfo - Inhalt 1": "",
            "Beleginfo - Art 2": "",
            "Beleginfo - Inhalt 2": "",
            "Beleginfo - Art 3": "",
            "Beleginfo - Inhalt 3": "",
            "Beleginfo - Art 4": "",
            "Beleginfo - Inhalt 4": "",
            "Beleginfo - Art 5": "",
            "Beleginfo - Inhalt 5": "",
            "Beleginfo - Art 6": "",
            "Beleginfo - Inhalt 6": "",
            "Beleginfo - Art 7": "",
            "Beleginfo - Inhalt 7": "",
            "Beleginfo - Art 8": "",
            "Beleginfo - Inhalt 8": "",
            "KOST1 - Kostenstelle": "",
            "KOST2 - Kostenstelle": "",
            "Kost-Menge": "",
            "EU-Mitgliedstaat u. UStIdNr": "",
            "EU-Steuersatz": "",
            "Abw. Versteuerungsart": "",
            "Sachverhalt L+L": "",
            "Funktionsergänzung L+L": "",
            "BU 49 Hauptfunktionstyp": "",
            "BU 49 Hauptfunktionsnummer": "",
            "BU 49 Funktionsergänzung": "",
            "Zusatzinformation - Art 1": "",
            "Zusatzinformation- Inhalt 1": "",
            "Zusatzinformation - Art 2": "",
            "Zusatzinformation- Inhalt 2": "",
            "Zusatzinformation - Art 3": "",
            "Zusatzinformation- Inhalt 3": "",
            "Zusatzinformation - Art 4": "",
            "Zusatzinformation- Inhalt 4": "",
            "Zusatzinformation - Art 5": "",
            "Zusatzinformation- Inhalt 5": "",
            "Zusatzinformation - Art 6": "",
            "Zusatzinformation- Inhalt 6": "",
            "Zusatzinformation - Art 7": "",
            "Zusatzinformation- Inhalt 7": "",
            "Zusatzinformation - Art 8": "",
            "Zusatzinformation- Inhalt 8": "",
            "Zusatzinformation - Art 9": "",
            "Zusatzinformation- Inhalt 9": "",
            "Zusatzinformation - Art 10": "",
            "Zusatzinformation- Inhalt 10": "",
            "Zusatzinformation - Art 11": "",
            "Zusatzinformation- Inhalt 11": "",
            "Zusatzinformation - Art 12": "",
            "Zusatzinformation- Inhalt 12": "",
            "Zusatzinformation - Art 13": "",
            "Zusatzinformation- Inhalt 13": "",
            "Zusatzinformation - Art 14": "",
            "Zusatzinformation- Inhalt 14": "",
            "Zusatzinformation - Art 15": "",
            "Zusatzinformation- Inhalt 15": "",
            "Zusatzinformation - Art 16": "",
            "Zusatzinformation- Inhalt 16": "",
            "Zusatzinformation - Art 17": "",
            "Zusatzinformation- Inhalt 17": "",
            "Zusatzinformation - Art 18": "",
            "Zusatzinformation- Inhalt 18": "",
            "Zusatzinformation - Art 19": "",
            "Zusatzinformation- Inhalt 19": "",
            "Zusatzinformation - Art 20": "",
            "Zusatzinformation- Inhalt 20": "",
            "Stück": "",
            "Gewicht": "",
            "Zahlweise": "",
            "Forderungsart": "",
            "Veranlagungsjahr": "",
            "Zugeordnete Fälligkeit": "",
            "Skontotyp": "",
            "Auftragsnummer": "",
            "Buchungstyp": "",
            "USt-Schlüssel (Anzahlungen)": "",
            "EU-Land (Anzahlungen)": "",
            "Sachverhalt L+L (Anzahlungen)": "",
            "EU-Steuersatz (Anzahlungen)": "",
            "Erlöskonto (Anzahlungen)": "",
            "Herkunft-Kz": "",
            "Buchungs GUID": "",
            "KOST-Datum": "",
            "SEPA-Mandatsreferenz": "",
            "Skontosperre": "",
            "Gesellschaftername": "",
            "Beteiligtennummer": "",
            "Identifikationsnummer": "",
            "Zeichnernummer": "",
            "Postensperre bis": "",
            "Bezeichnung SoBil-Sachverhalt": "",
            "Kennzeichen SoBil-Buchung": "",
            "Festschreibung": "",
            "Leistungsdatum": "",
            "Datum Zuord. Steuerperiode": "",
            "Fälligkeit": "",
            "Generalumkehr (GU)": "",
            "Steuersatz": "",
            "Land": "",
        }
