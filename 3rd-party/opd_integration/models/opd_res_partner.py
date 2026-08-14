# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResPartnerInherit(models.Model):
    """
       Description:
           This class inherits the 'res.partner' model and adds additional functionality for fetching
           company data from Pipedrive and updating records in Odoo.

       Methods:
           fetch_company_from_pipedrive(instance_id, last_sync_date):
               Fetches company data from Pipedrive and updates records in Odoo.

       """
    _inherit = 'res.partner'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_id = fields.Char(string='Pipedrive ID')
    sync_to_pipedrive = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Sync To Pipedrive', default='yes')
    odoo_hash = fields.Char(string='Odoo hash')

    @api.model
    def fetch_company_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches company data from Pipedrive and updates records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive Company Last Sync Date.
        #        """
        return self.env['opd.mapper.mixin'].fetch_partner_data_from_pipedrive(instance_id, 'organizations',
              'res.partner','pipedriveinstance.companies.lines','opd.companymapper', last_sync_date,'is_company_calls',
              'is_company_tasks', 'is_company_emails','is_company_meetings','is_company_notes',
              'org', 'organization', True,'pipedrive_company_dropdown_mapping','company', operation_type)

    @api.model
    def fetch_contact_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches company data from Pipedrive and updates records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive Company Last Sync Date.
        #        """
        return self.env['opd.mapper.mixin'].fetch_partner_data_from_pipedrive(instance_id, 'persons',
               'res.partner','pipedriveinstance.contacts.lines', 'opd.contactmapper', last_sync_date,'is_contact_calls',
               'is_contact_tasks','is_contact_emails','is_contact_meetings','is_contact_notes', 'people', 'person',
                False,'pipedrive_contacts_dropdown_mapping','contact', operation_type)

    @api.model
    def fetch_company_from_odoo(self, instance_id, last_sync_date, operation_type):
        """
            Fetches company data from Odoo and stores it in Pipedrive.

            Args:
                instance_id (int): The ID of the Pipedrive instance.
                last_sync_date (str): The date of the last synchronization.

            Returns:
                dict: Result of the data fetch operation from Odoo.

        """
        return self.env['opd.mapper.mixin'].fetch_all_odoo_partner_data(instance_id, 'res.partner', last_sync_date,
                                                                'organizations', 'pipedriveinstance.companies.lines',
                                                                'opd.companymapper', 'org', 'organization',
                                                                'odoo_company_dropdown_mapping', True, 'company', operation_type)

    @api.model
    def fetch_contact_from_odoo(self, instance_id, last_sync_date, operation_type):
        """
            Fetches contact data from Odoo and stores it in Pipedrive.

            Args:
                instance_id (int): The ID of the Pipedrive instance.
                last_sync_date (str): The date of the last synchronization.

            Returns:
                dict: Result of the data fetch operation from Odoo.

        """
        return self.env['opd.mapper.mixin'].fetch_all_odoo_partner_data(instance_id, 'res.partner', last_sync_date,
                                                                'persons', 'pipedriveinstance.contacts.lines',
                                                                'opd.contactmapper', 'people', 'person',
                                                                'odoo_contacts_dropdown_mapping', False, 'contact', operation_type)

    # ------------- Method to transfer company data from Odoo to Pipedrive ------------- #
    def transfer_company_data(self, odoo_record, instance_id, field_model_name, dropdown_mapping_field,
                              pipedrive_model_name, type, object, logger_name, operation_type):
        try:

            result = self.env['opd.mapper.mixin'].handle_company_record(instance_id, odoo_record, field_model_name,
                                                                        pipedrive_model_name,
                                                                        'opd.companymapper', dropdown_mapping_field,
                                                                        'res.partner', type, object, logger_name, operation_type,
                                                                        check_hash=False)
            return result

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} transfer in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, '',
                                                             error_type)
            return None

    # ---------------- Send Record To Pipedrive From Partner Form And Tree View ------------------ #

    def partner_record_send_to_pipedrive(self):
        """
            Sends partner records from Odoo to Pipedrive. Handles both company and contact records, and logs the process.

            This function processes active partner records in the current context and sends them to Pipedrive. It
            handles the creation or updating of these records in Pipedrive and logs the results.

            Returns:
                str: A notification message indicating the result of the synchronization process.
        """
        logger_name, record_id = None, None
        # # Ensure active_ids are passed in correctly
        active_ids = self._context.get('active_ids', [self.id]) if self._context.get('active_ids') else [self.id]
        if len(active_ids) > 10:
            raise ValidationError(
                "You can only sync up to 10 records at a time to Pipedrive. Please select 10 or fewer records and try again.")
        try:
            # Call test_connection to check if the connection is successful
            current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)

            if not current_instance:
                _logger.error('No current Pipedrive instance found.')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Pipedrive Instance Not Found'),
                        'message': 'No current Pipedrive instance found. Please configure a Pipedrive instance first.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            instance_id = current_instance
            success = True
            created_records, updated_records, no_update_records = 0, 0, 0
            contact_email = None

            if not active_ids:
                active_ids = [self.id]

            for record_id in active_ids:
                record = self.browse(record_id)
                # Set logger_name based on record type
                logger_name = 'company' if record.is_company else 'contact'
                notification, is_connected = current_instance.sync_record_test_connection('pipedrive', logger_name, current_instance, 'manually')

                # If the connection failed (is_connected is False), return the notification
                if not is_connected:
                    return notification

                if record.sync_to_pipedrive != 'yes' or record.active is not True:
                    if record.sync_to_pipedrive != 'yes':
                        warning_message = f'Sync to Pipedrive is required to be "Yes" for record ID {record_id}.'
                    else:
                        warning_message = f'Archived record is not send odoo to pipedrive, record ID {record_id}.'
                    operation = f'Manual {logger_name.capitalize()} Push Odoo To Pipedrive'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                       'pipedrive', record, 'manually', record_id)
                    success = False
                    continue

                if record.is_company:
                    result = self.transfer_company_data(record, instance_id, 'pipedriveinstance.companies.lines',
                                                        'odoo_company_dropdown_mapping', 'organizations', 'org',
                                                        'organization',
                                                        'company', 'manually')

                    created_records, updated_records, no_update_records, success = self.handle_result(result,
                                                                                                      created_records,
                                                                                                      updated_records,
                                                                                                      no_update_records,
                                                                                                      success)

                else:  # Assumes the record is a contact
                    result, pipedrive_record_id, org_id, partner_org_id, contact_id, contact_email, dynamic_fields_values_hash = \
                        self.env[
                            'opd.mapper.mixin'].transfer_contact_data(record, instance_id,
                            'pipedriveinstance.contacts.lines','odoo_contacts_dropdown_mapping', 'persons',
                            'opd.contactmapper', 'people','person', 'contact', 'manually', check_hash=False)
                    if result is not None and result != 'no_action':
                        self.env['opd.mapper.mixin'].handle_activities_and_notes(instance_id, record, 'manually',
                                                                                 is_contact=True, is_activity=False)
                        self.env['opd.mapper.mixin'].handle_contact_related_data(instance_id, contact_id,
                                                                                 partner_org_id,
                                                                                 pipedrive_record_id, 'manually')
                    created_records, updated_records, no_update_records, success = self.handle_result(result,
                                                                                                      created_records,
                                                                                                      updated_records,
                                                                                                      no_update_records,
                                                                                                      success)
                if result == 'no_action':
                    warning_message = f'The email ID {contact_email} is already associated with another contact. Please use a different email ID.'
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Record Not Synced Successful'),
                            'message': f'Data not synced successfully to {logger_name}, {warning_message}',
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
            # Generate a consolidated notification after processing all records
            return self.env['res.partner'].generate_sync_notification(success, 'pipedrive', logger_name, created_records,
                                                                      updated_records, no_update_records)

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', 'manually', record_id,
                                                             error_type)
            return None

    # -----------------  Handle the result of the data transfer operation. ------------------ #
    @api.model
    def handle_result(self, result, created_records, updated_records, no_update_records, success):
        """
        Handle the result of the data transfer operation.

        Args:
            result (str): The result of the operation ('create', 'update', 'no_update', or 'skip').
            created_records (int): The count of created records.
            updated_records (int): The count of updated records.
            no_update_records (int): The count of records that did not require updates.

        Returns:
            tuple: A tuple containing the updated counts and success flag.
        """
        if result == 'create':
            created_records += 1
        elif result == 'update':
            updated_records += 1
        elif result == 'no_update':
            no_update_records += 1
        else:
            success = False

        return created_records, updated_records, no_update_records, success

    # ---------------------- Generate a synchronization notification ---------------------- #
    def generate_sync_notification(self, success, model_name, logger_name, created_records=0, updated_records=0,
                                   no_update_records=0):
        """
                Generate a synchronization notification.

                This method creates a notification message based on the synchronization results. It constructs a message
                detailing the number of records created, updated, and not requiring updates during the synchronization
                process. Depending on the success of the synchronization, it returns a notification action with either
                a success or partial success message.

                Args:
                    success (bool): Indicates whether the synchronization was successful.
                    model_name (str): The name of the model to which data was synced.
                    created_records (int, optional): The number of records that were created. Default is 0.
                    updated_records (int, optional): The number of records that were updated. Default is 0.
                    no_update_records (int, optional): The number of records that did not require updates. Default is 0.

                Returns:
                    dict: A dictionary containing the notification action. The action includes the type of notification
                          (success or danger), the title, the message, and whether the notification is sticky or not.

                """
        message = ''
        if created_records:
            message += f'{logger_name.capitalize()} record created. '
        if updated_records:
            message += f'{logger_name.capitalize()} record updated. '
        if no_update_records:
            message += f' {logger_name.capitalize()} record did not require updates. '

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Successful'),
                    'message': f'{logger_name.capitalize()} synced successfully to {model_name.capitalize()}, {message}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sync Partially Successful'),
                    'message': f'Failed to sync odoo {logger_name} to {model_name}, {message}',
                    'type': 'danger',
                    'sticky': False,
                }
            }
