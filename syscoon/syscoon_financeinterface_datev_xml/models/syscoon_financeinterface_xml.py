# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from lxml import etree
from odoo import fields, models


class SyscoonFinanceinterfaceXML(models.AbstractModel):
    _name = "syscoon.financeinterface.xml"
    _description = "definitions for the syscoon financeinterface DATEV XML-export"

    def create_invoice_xml(self, move_id, invoice_mode):
        xml = self.make_invoice_xml(move_id, invoice_mode)
        invoice = etree.tostring(
            xml, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )
        return invoice

    def make_invoice_xml(self, move_id, invoice_mode):
        attr_qname = etree.QName(
            "http://www.w3.org/2001/XMLSchema-instance", "schemaLocation"
        )
        nsmap = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            None: "http://xml.datev.de/bedi/tps/invoice/v050",
        }

        invoice = etree.Element(
            "invoice",
            {
                attr_qname: "http://xml.datev.de/bedi/tps/invoice/v050 "
                "Belegverwaltung_online_invoice_v050.xsd"
            },
            nsmap=nsmap,
        )
        invoice.attrib["generator_info"] = "Odoo 18"
        invoice.attrib["generating_system"] = "Odoo-ERP Software"
        invoice.attrib["description"] = "DATEV Import invoices"
        invoice.attrib["version"] = "5.0"
        invoice.attrib[
            "xml_data"
        ] = "Kopie nur zur Verbuchung berechtigt nicht zum Vorsteuerabzug"
        interface = self.env["syscoon.financeinterface"]
        template = interface._export_template()

        def _apply_template_line_config(template_keys, key, val):
            return interface._apply_template_line_config(move_id, template_keys, key, val)

        data = {
            "move": move_id,
            "mode": invoice_mode,
            "element": invoice,
            "template": template,
            "template_keys": template._template_vals(line_type="xml"),
            "key_apply": _apply_template_line_config,
        }
        move_id._process_datev_xml_all(data)
        return invoice

    def create_documents_xml(self, docs, invoice_mode):
        xml = self.make_documents_xml(docs, invoice_mode)
        documents = etree.tostring(
            xml, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )
        return documents

    def make_documents_xml(self, docs, invoice_mode):
        attr_qname = etree.QName(
            "http://www.w3.org/2001/XMLSchema-instance", "schemaLocation"
        )
        qname = etree.QName("http://www.w3.org/2001/XMLSchema-instance", "type")
        nsmap = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            None: "http://xml.datev.de/bedi/tps/document/v05.0",
        }
        archive = etree.Element(
            "archive",
            {
                attr_qname: "http://xml.datev.de/bedi/tps/document/v05.0 "
                "document_v050.xsd"
            },
            nsmap=nsmap,
        )
        archive.attrib["version"] = "5.0"
        archive.attrib["generatingSystem"] = "Odoo-ERP Software"
        header = etree.SubElement(archive, "header")
        date = etree.SubElement(header, "date")
        date.text = fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        description = etree.SubElement(header, "description")
        description.text = "Rechnungsexport"
        content = etree.SubElement(archive, "content")
        if invoice_mode == "bedi":
            for doc in docs:
                document = etree.SubElement(content, "document")
                if doc.inv.datev_bedi:
                    document.attrib["guid"] = doc.inv.datev_bedi
                extension = etree.Element("extension", {qname: "File"})
                extension.attrib["name"] = doc.pdf_path
                document.append(extension)
        else:
            for doc in docs:
                document = etree.SubElement(content, "document")
                extension = etree.Element("extension", {qname: "Invoice"})
                extension.attrib["datafile"] = doc.xml_path
                tree_property = etree.SubElement(extension, "property")
                tree_property.attrib["key"] = "InvoiceType"
                tree_property.attrib["value"] = doc.inv._get_datev_xml_document_value()
                document.append(extension)
                extension = etree.Element("extension", {qname: "File"})
                extension.attrib["name"] = doc.pdf_path
                document.append(extension)
        return archive
