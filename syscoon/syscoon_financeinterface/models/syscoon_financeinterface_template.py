# © 2025 syscoon Estonia OÜ (<https://syscoon.com>)
# License OPL-1, See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class SyscoonFinanceinterfaceTemplate(models.Model):
    """The class syscoon.financeinterface is the central object to generate
    exports for the selected moves that can be used to be imported in the
    different financial programms on different ways"""

    _name = "syscoon.financeinterface.template"
    _description = "syscoon Financial Interface  Export Template"
    _order = "name desc"

    name = fields.Char(required=True, readonly=False)
    belegfeld_1_use_ref = fields.Boolean(string="Use Customer Reference")
    line_ids = fields.One2many(
        comodel_name="syscoon.financeinterface.template.line",
        inverse_name="template_id",
        domain=[("type", "=", "ascii")],
    )
    xml_line_ids = fields.One2many(
        comodel_name="syscoon.financeinterface.template.line",
        inverse_name="template_id",
        domain=[("type", "=", "xml")],
    )

    def _template_vals(self, line_type="ascii"):
        """Returns the name and description of syscoon.financeinterface.template.line as a dictionary."""
        if hasattr(self, f"_{line_type}_template_vals"):
            return getattr(self, f"_{line_type}_template_vals")()
        return {}

    def _ascii_template_vals(self):
        """Returns the name and description of syscoon.financeinterface.template.line as a dictionary."""
        return self.line_ids._get_vals()

    def _xml_template_vals(self):
        """Returns the name and description of syscoon.financeinterface.template.line as a dictionary."""
        return self.xml_line_ids._get_vals()


class SyscoonFinanceinterfaceTemplateLine(models.Model):
    """The class syscoon.financeinterface is the central object to generate
    exports for the selected moves that can be used to be imported in the
    different financial programms on different ways"""

    _name = "syscoon.financeinterface.template.line"
    _description = "syscoon Financial Interface  Template Lines"
    _order = "sequence asc"

    name = fields.Char(string="Heading", required=True)
    sequence = fields.Integer(required=True, string="line#")
    expression = fields.Char(required=False)
    description = fields.Text()
    type = fields.Selection(
        [
            ("ascii", "ASCII"),
            ("xml", "XML"),
        ],
        default="ascii",
        required=True,
    )
    value_code = fields.Char(
        string="Force Value",
        help="Force a value for this field it can be evaluated from the move/line",
    )
    template_id = fields.Many2one(
        comodel_name="syscoon.financeinterface.template",
        readonly=True,
        ondelete="cascade",
    )

    def _get_vals(self):
        return {
            line.name: {"expression": line.expression, "force_value": line.value_code}
            for line in self
        }
