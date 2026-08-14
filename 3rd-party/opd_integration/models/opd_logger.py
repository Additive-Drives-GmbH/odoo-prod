from odoo import api, fields, models
import datetime
from datetime import datetime, timedelta


class PipedriveLogger(models.Model):
    """
        The PipedriveLogger class is an Odoo model designed for logging interactions between Odoo and Pipedrive.
        The class captures detailed information about the integration processes, including the direction of integration,
         module name, execution time, user details, operation specifics, and payloads for requests and responses.
         Additionally, it logs error codes and details, and tracks the resolution status and log type
    """
    _name = "opd_integration.pipedrivelogger"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Pipedrive Logger"
    _rec_name = 'integration_direction'
    _order = 'id desc'

    integration_direction = fields.Selection(
        [('otp', 'Odoo To Pipedrive'), ('pto', 'Pipedrive To Odoo')], string='Integration Direction', tracking=True)
    module_name = fields.Selection(
        [('contacts', 'Contacts'), ('companies', 'Companies'), ('deals', 'Opportunities'), ('leads', 'Leads'),
         ('products', 'Products'), ('users', 'Users'), ('activities', 'Activities'), ('notes', 'Notes'), ('files', 'Files'), ('mailmessage', 'mailMessage'), ('associations', 'Associations'), ('leadLabels', 'Lead Labels')],
        string='Module Name', tracking=True)
    operation_performed_by = fields.Selection(
        [('schedular', 'Schedular'), ('manually', 'Manually')],
        string='Operation Type', tracking=True)
    pipedrive_datetime = fields.Datetime(string="Execution DateTime", default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string="User Id", tracking=10)
    record_id = fields.Char(string='Record ID')
    operation = fields.Char(string='Operation', tracking=True)
    description = fields.Text(string='Description', tracking=True)
    error_code = fields.Char(string='Status Code', tracking=True)
    error_details = fields.Text(string='Error Details', tracking=True)
    request_payload = fields.Text(string='Request Payload', tracking=True)
    response_payload = fields.Text(string='Response Payload', tracking=True)
    resolution_status = fields.Selection(
        [('pending', 'Pending'), ('resolve', 'Resolve')], string='Resolution Status', tracking=True)
    log_type = fields.Selection(
        [('error', 'Error'), ('success', 'Success'), ('warning', 'Warning'), ('info', 'Info')], string='Log Type', tracking=True)

    @api.model
    def _cron_delete_old_log_records(self):
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        try:
            notification, is_connected = self.env['opd.pipedriveinstance'].sync_record_test_connection('',
                                                                                         '', current_instance,
                                                                                         'schedular')
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            if is_connected:
                remove_log_scheduler = current_instance.remove_log_scheduler
                remove_log_month = current_instance.remove_log_month
                if remove_log_scheduler:
                    months_ago = int(remove_log_month or 1)
                    date_threshold = datetime.now() - timedelta(days=30 * months_ago)
                    old_records = self.env['opd_integration.pipedrivelogger'].search([('pipedrive_datetime', '<', date_threshold)])
                    old_records.unlink()

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while delete logger records'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, '', description, '', 'schedular', '',
                                                             error_type)
            return None

    def create_logger(self, error_details, error_code, integration_direction, module_name, description, request_payload,
                      response_payload, operation, resolution_status, log_type, operation_performed_by, record_id):
        """
           Create a new log record for Pipedrive integration.

           This method creates a new log record in the `opd_integration.pipedrivelogger` model
           with the provided details. It includes information about errors, integration direction,
           module name, operation details, request and response payloads, and resolution status.

           Args:
               error_details (str): Details of the error encountered.
               error_code (str): Code representing the error.
               integration_direction (str): Direction of integration ('otp' for Odoo to Pipedrive,
                                            'pto' for Pipedrive to Odoo).
               module_name (str): Name of the Pipedrive module involved in the integration.
               description (str): Description of the integration process.
               request_payload (str): Payload of the request sent to Pipedrive.
               response_payload (str): Payload of the response received from Pipedrive.
               operation (str): Operation performed during the integration.
               resolution_status (str): Status of the resolution ('pending' or 'resolve').
               log_type (str): Type of log ('error', 'success', or 'warning').

           Returns:
               recordset: The created log record.
           """
        error_data = {
            'error_details': error_details,'error_code': error_code,'integration_direction': integration_direction,
            'module_name': module_name,'description': description,'request_payload': request_payload,
            'response_payload': response_payload,'operation': operation,'resolution_status': resolution_status,
            'log_type': log_type, 'operation_performed_by': operation_performed_by, 'record_id': record_id,}
        logger_record = self.env['opd_integration.pipedrivelogger'].create(error_data)
        logger_record.env.cr.commit()
