from odoo import api, fields, models


# Description
class CompanyMapper(models.Model):
    """
        CompanyMapper Model
        This model represents a mapping between company fields in Odoo and Pipedrive.
    """
    _name = "opd.companymapper"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Company Mapper"
    _rec_name = 'label_name'

    field_id = fields.Char(string='Field ID', tracking=True)
    label_name = fields.Char(string='Label Name', tracking=True)
    field_type = fields.Char(string='Field Type', tracking=True)
    pipedrive_instance_name = fields.Char(string='Instance Name', tracking=True)
    system_name = fields.Char(string='System Name', tracking=True)
    internal_name = fields.Char(string='Internal Name')
    field_definition = fields.Text(string='Field Description')


    @api.model
    def fetch_and_store_company_fields(self):
        return self.env['opd.mapper.mixin'].fetch_and_store_fields(
            'res_partner','organizationFields',self.env['opd.companymapper'],'company', 'companymapper_id', 'pipedriveinstance.companies.lines')

    class PipedriveFilter(models.Model):
        _name = 'opd.filter'
        _description = 'Pipedrive Created Filters'
        _order = 'create_date desc'

        filter_id = fields.Char(string="Filter ID", required=True, index=True)
