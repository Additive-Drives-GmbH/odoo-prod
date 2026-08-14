from odoo import api, fields, models


class ContactMapper(models.Model):
    """
        ContactMapper Model
        This model represents a mapping between contact fields in Odoo and Pipedrive.
    """
    _name = "opd.contactmapper"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Contact Mapper"
    _rec_name = 'label_name'

    field_id = fields.Char(string='Field ID', tracking=True)
    label_name = fields.Char(string='Label Name', tracking=True)
    field_type = fields.Char(string='Field Type', tracking=True)
    pipedrive_instance_name = fields.Char(string='Instance Name', tracking=True)
    system_name = fields.Char(string='System Name', tracking=True)
    internal_name = fields.Char(string='Internal Name')
    field_definition = fields.Text(string='Field Description')


    @api.model
    def fetch_and_store_contact_fields(self):
        return self.env['opd.mapper.mixin'].fetch_and_store_fields(
            'res_partner','personFields',self.env['opd.contactmapper'],'contact', 'contactmapper_id', 'pipedriveinstance.contacts.lines')