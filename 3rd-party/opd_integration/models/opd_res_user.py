# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
from datetime import datetime
import pytz
import json
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResUserInherit(models.Model):
    """
       Description:
           This class inherits the 'res.users' model and adds additional functionality for fetching
           users data from Pipedrive and updating records in Odoo.

       """
    _inherit = 'res.users'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_id = fields.Char(string='Pipedrive ID')
    odoo_hash = fields.Char(string='Odoo hash')

    @api.model
    def fetch_users_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        """
           Description:
               Fetches company data from Pipedrive and updates records in Odoo.

           Args:
               instance_id (str): The Pipedrive instance ID.
               last_sync_date (Datetime): The Pipedrive Company Last Sync Date.
        """
        user_id = None
        try:
            user_timezone = self.env.user.tz or 'UTC'

            # Get the current IST time
            now_ist = datetime.now(pytz.timezone(user_timezone))

            now_utc = now_ist.astimezone(pytz.utc)
            if not last_sync_date:
                last_sync_date = now_utc.replace(tzinfo=None)

            last_sync_date = str(last_sync_date)
            last_sync_date_str = None

            try:
                last_sync_date_str = self.parse_date(last_sync_date)
            except ValueError as e:
                _logger.info("Error parsing date: {e}")

            # Set a temporary variable to store the current UTC time at the start of the function
            current_utc_time = datetime.utcnow()

            api_token = instance_id.api_token if 'api_token' in instance_id else None

            while True:
                endpoint = f'{self.__API_BASE_URL}users?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                payload_rec = {}

                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")

                if response.status_code == 200:
                    response_json = response.json()
                    records = response_json.get('data', [])

                    if not records:
                        break  # No records found, exit the loop

                    for record in records:
                        record_modified_date = record.get('modified')
                        active_user = record.get('active_flag')
                        record_modified_date_str = datetime.strptime(record_modified_date, "%Y-%m-%d %H:%M:%S")
                        if record_modified_date_str > last_sync_date_str and active_user:
                            user_id = record.get('id')
                            user_email = record.get('email')
                            user_name = record.get('name')
                            temp_data = {'login': user_email, 'name': user_name}
                            mapped_data = self.env['opd.mapper.mixin'].prepare_mapped_data_pipedrive_and_odoo(temp_data,
                                                                                                              mapping=None)
                            dynamic_fields_values_hash = self.env['opd.mapper.mixin'].calculate_hash(mapped_data)
                            record_data = {'pipedrive_id': user_id, 'login': user_email, 'name': user_name,
                                           'odoo_hash': dynamic_fields_values_hash}
                            user_record = self.env['res.users'].search(
                                [('login', '=', user_email), ('active', '=', True)])

                            if user_record:
                                if user_record.odoo_hash != dynamic_fields_values_hash:
                                    user_record.write(record_data)
                                    user_record.env.cr.commit()
                                    self.env['opd.mapper.mixin'].log_operation('user', '', user_id, record_data,
                                    'update', 'odoo', operation_type, parent_name=None,parent_id=None)
                                else:
                                    _logger.info(f'No update required for this user')
                            else:
                                user_record = self.env['res.users'].create(record_data)
                                user_record.env.cr.commit()
                                self.env['opd.mapper.mixin'].log_operation('user', '', user_id, record_data,
                                'create', 'odoo', operation_type, parent_name=None,parent_id=None)

                    if last_sync_date:
                        instance_id.write({'pipedrive_users_last_sync_date': current_utc_time})
                        self.env['opd.mapper.mixin'].scheduler_run_successfully_log('user', operation_type,
                                                                                    'odoo')
                    break
                else:
                    # Log the error with HTTP status code
                    description = f'Error occurred while fetching user records'
                    self.env['opd.mapper.mixin'].http_log_error(f"No record found: {response.text}", 'user',
                    description,payload_rec, response.text, 'odoo', operation_type, user_id,
                                                                f"HTTP {response.status_code}")
                    break

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while user create/update in the Odoo.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'user', description, 'odoo', operation_type, user_id, error_type)

    # --------------------------- Parse Last Sync Date Of Pipedrive User -------------------------- #
    def parse_date(self, date_str):
        try:
            # Try parsing with microseconds first
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            # Fall back to parsing without microseconds
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

    # ------------------- Fetch User Form Odoo And Send To Pipedrive ---------------- #

    @api.model
    def fetch_users_from_odoo(self, instance_id, last_sync_date, operation_type):
        """
           Description:
               Fetches user data from Pipedrive and updates records in Odoo.

           Args:
               instance_id (str): The Pipedrive instance ID.
               last_sync_date (Datetime): The Pipedrive Company Last Sync Date.
        """

        try:
            # Set a temporary variable to store the current UTC time at the start of the function
            last_sync_date, current_utc_time = self.env['opd.mapper.mixin'].last_sync_date_common(last_sync_date)
            api_token = instance_id.api_token if 'api_token' in instance_id else None

            while True:
                records = self.env['res.users'].search_read(
                    domain=[('write_date', '>', last_sync_date), ('share', '=', False), ('active', '=', True)],
                    fields=['name', 'login', 'id', 'odoo_hash'],
                    order='write_date desc'
                )
                if not records:
                    break  # No records found, exit the loop

                for record in records:
                    self.sync_user_record_to_pipedrive(record, api_token, instance_id, operation_type)
                break

                # Update the last sync date in the instance configuration
            instance_id.write({'odoo_users_last_sync_date': current_utc_time})
            self.env['opd.mapper.mixin'].scheduler_run_successfully_log('user', operation_type,
                                                                        'pipedrive')

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while user create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'user', description, 'pipedrive', operation_type, '',
                                                             error_type)

    # ----------------------- Send Single User Record To Pipedrive ---------- #
    def sync_user_record_to_pipedrive(self, record, api_token, instance_id, operation_type):
        """
        Sends a single record to Pipedrive.

        Args:
            record (recordset): The Odoo record to send to Pipedrive.
            api_token (str): The API token for authenticating with Pipedrive.

        Returns:
            str: Result of the operation ('created', 'updated', or 'error').
        """
        try:
            user_id = record['id']
            user_email = record['login']
            user_name = record['name']
            temp_data = {'email': user_email, 'name': user_name}
            mapped_data = self.env['opd.mapper.mixin'].prepare_mapped_data_pipedrive_and_odoo(temp_data, mapping=None)

            # Calculating Hash
            dynamic_fields_values_hash = self.env['opd.mapper.mixin'].calculate_hash(mapped_data)
            record_data = {'email': user_email, 'name': user_name, 'active_flag': 'true'}
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            # Check if the record exists in Pipedrive
            all_pipedrive_records = self.fetch_all_pipedrive_records(instance_id)
            is_existing, pipedrive_user_id = self.is_record_in_pipedrive(user_email, all_pipedrive_records)

            if is_existing:
                # Record already exists in Pipedrive, update it
                if record['odoo_hash'] != dynamic_fields_values_hash:
                    update_endpoint = f'{self.__API_BASE_URL}users/{pipedrive_user_id}?api_token={api_token}'
                    update_payload = json.dumps(record_data)
                    response = requests.put(update_endpoint, headers=headers, data=update_payload)

                    if response.status_code == 200:
                        write_record = self.env['res.users'].browse(user_id)
                        write_record.write({'pipedrive_id': pipedrive_user_id, 'odoo_hash': dynamic_fields_values_hash})
                        write_record.env.cr.commit()
                        self.env['opd.mapper.mixin'].log_operation('user', response.status_code, user_id,
                         record_data, 'update','pipedrive', operation_type, parent_name=None,parent_id=None)
                        return 'update'
                    else:
                        self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}",
                        'user',f"Failed to update user in Pipedrive",record_data,response.text, 'pipedrive',
                        operation_type, user_id,f"HTTP {response.status_code}")
                        return 'error'
                else:
                    return 'no_update'
            else:
                create_endpoint = f'{self.__API_BASE_URL}users?api_token={api_token}'
                create_payload = json.dumps(record_data)
                response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, create_payload,
                                                                   method="POST")
                if response.status_code == 200:
                    response_json = response.json()
                    new_record = response_json.get('data', {})
                    pipedrive_id = new_record.get('id')
                    # Retrieve the recordset using browse
                    user_record = self.env['res.users'].browse(user_id)
                    user_record.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
                    user_record.env.cr.commit()
                    self.env['opd.mapper.mixin'].log_operation('user', response.status_code, user_id, record_data,
                    'create','pipedrive', operation_type, parent_name=None,parent_id=None)
                    return 'create'
                else:
                    self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}",
                     'user',f"Failed to create user in pipedrive",record_data,
                     response.text, 'pipedrive', operation_type, user_id,f"HTTP {response.status_code}")
                    return 'error'
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while user create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'user', description, 'pipedrive', operation_type, record['id'],
                                                             error_type)
            return None

    # ---------------------- Fetch all records from Pipedrive --------------- #
    def fetch_all_pipedrive_records(self, instance_id):
        """
            Fetch all records from Pipedrive.
        """
        api_token = instance_id.api_token if 'api_token' in instance_id else None
        endpoint = f'{self.__API_BASE_URL}users?api_token={api_token}'
        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            response_json = response.json()
            return response_json.get('data', [])
        else:
            return []

    # ---------------- Send Record To Pipedrive From User Form And Tree View ------------------ #

    def user_send_to_pipedrive(self):
        """
            Synchronizes selected user records from Odoo to Pipedrive.

            This method processes active user records in the current context, synchronizes them with Pipedrive,
            and logs the results of the synchronization process. It handles both the creation and updating of
            user records in Pipedrive and logs any warnings or errors that occur.

            Returns:
                str: A notification message indicating the result of the synchronization process, including
                     the number of created, updated, and no-update records.
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
            notification, is_connected = current_instance.sync_record_test_connection('pipedrive', 'user', current_instance, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            if not current_instance:
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
            api_token = current_instance.api_token
            success = True
            created_records, updated_records, no_update_records = 0, 0, 0

            for record_id in active_ids:
                record = self.browse(record_id)
                if not record.active or not record.share == False:
                    if not record.share == False:
                        warning_message = f'User is a regular internal user record ID {record_id}.'
                    else:
                        warning_message = f'Archived record is not send odoo to pipedrive, record ID {record_id}.'
                    operation = f'Manual User Push Odoo To Pipedrive'
                    self.env['opd.mapper.mixin'].log_operation_warning('user', warning_message, operation, 'pipedrive', record, 'manually', record_id)
                    success = False
                    continue
                result = self.sync_user_record_to_pipedrive(record, api_token, current_instance, 'manually')
                created_records, updated_records, no_update_records, success = self.env[
                    'res.partner'].handle_result(result,created_records,updated_records,no_update_records, success)

            return self.env['res.partner'].generate_sync_notification(success, 'pipedrive', 'user', created_records,
                                                                      updated_records, no_update_records)
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while user create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'user', description, 'pipedrive', 'manually', record_id,
                                                             error_type)
            return None

    # --------------- Check Record Is In Pipedrive Or Not ----------------- #
    @api.model
    def is_record_in_pipedrive(self, email, all_pipedrive_records):
        """
            Check if a user record exists in Pipedrive based on email.

            This method iterates through the provided list of Pipedrive records to find a record
            with a matching email address.

            Args:
                email (str): The email address to check for in the Pipedrive records.
                all_pipedrive_records (list): A list of dictionaries representing Pipedrive records.

            Returns:
                tuple: A tuple containing a boolean indicating if the record exists, and the Pipedrive
                       user ID if the record is found (None otherwise).
        """

        for record in all_pipedrive_records:
            if record.get('email') == email:
                user_id = record.get('id')
                return True, user_id
        return False, None

    # --------------------------- Get User Record Method --------------------- #
    def get_user_record(self, record, key='owner_id'):
        """
            Retrieve a user record from Odoo based on Pipedrive ID.
            Safe for v1/v2 records — missing owner fields return None, never raise.
        """
        user = self.env['opd.mapper.mixin'].get_odoo_user_from_pipedrive_record(record, key)
        return user or None

    def get_lead_user_record(self, record, key='owner_id'):
        """Retrieve Odoo user for a Pipedrive lead/deal owner field."""
        return self.get_user_record(record, key)

    # ------------------------- Set Owner In Pipedrive -------------------- #
    def set_record_data(self, record, user_id_key, set_key, record_data):
        """
            Set the record data for the given keys.

            Args:
                record (dict): The record dictionary containing user data.
                user_id_key (str): The key to access the user ID in the record.
                set_key (str): The key to set in the record_data.
                record_data (dict): The dictionary where the set_key value will be stored.

            Returns:
                None
        """

        user_id = record.get(user_id_key) if isinstance(record, dict) else getattr(record, user_id_key, None)
        user_id_value = None
        # Check if user_id is a tuple and extract the ID if it is
        if user_id:
            if isinstance(user_id, tuple):
                user_id_value = user_id[0]  # Extract the user ID from the tuple
            else:
                user_id_value = user_id.id

        if user_id_value:
            user_record = self.env['res.users'].search(
                [('id', '=', user_id_value), ('share', '=', False), ('active', '=', True)], limit=1)
            user_pipedrive_id = user_record.pipedrive_id
            if user_pipedrive_id:
                record_data[set_key] = int(user_pipedrive_id)
        return user_id_value
