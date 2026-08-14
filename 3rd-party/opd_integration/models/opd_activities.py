# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
import json

class MailActivityInherit(models.Model):
    """
       Description:
           This class inherits the 'mail.activity' model and adds additional field for fetching pipedrive activity ID.
           This class contains methods for fetching activities and notes from Odoo and syncing them with Pipedrive.

       """
    _inherit = 'mail.activity'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_activity_id = fields.Char(string='Activity ID', readonly=True)

    @api.model
    def fetch_activity_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches activity data from Pipedrive and updates records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive Activity Last Sync Date.
        #        """
        return self.env['opd.mapper.mixin'].fetch_all_pipedrive_activities(instance_id, last_sync_date, 'opd.activitymapper', 'activity',
                                                                           'activity', operation_type)



    @api.model
    def get_record_type(self, odoo_record):
        """
        Determine the record type (organization, person, lead, or deal) based on the Odoo record.

        Args:
            odoo_record (object): Odoo record object.

        Returns:
            str: Record type ('organization', 'person', 'lead', or 'deal').
        """
        if odoo_record._name == 'res.partner':
            return 'organization' if odoo_record.is_company else 'person'
        elif odoo_record._name == 'crm.lead':
            return 'lead' if odoo_record.type == 'lead' else 'deal'
        return None

    # ------------------------- Get Pipedrive Activity Type ------------------------ #
    def get_pipedrive_activity_type(self, activity_type):
        """
        Map Odoo activity type to Pipedrive activity type.

        Args:
            activity_type (str): Name of the activity type in Odoo.

        Returns:
            str: Pipedrive activity type corresponding to the Odoo activity type.
        """
        activity_type_mapping = {
            'Call': 'call',
            'Email': 'email',
            'Meeting': 'meeting',
            'To-Do': 'task'
        }
        return activity_type_mapping.get(activity_type.name)

    # ------------ Check if the activity type is enabled by the user ---------- #
    @api.model
    def is_activity_enabled(self, instance_id, activity_type):
        """
        Check if the activity type is enabled by the user.

        Args:
            instance_id (object): Instance of the Pipedrive configuration.
            activity_type (str): Name of the activity type in Odoo.

        Returns:
            bool: True if the activity type is enabled, False otherwise.
        """
        activity_type_mapping = {
            'Call': instance_id.is_calls,
            'Email': instance_id.is_emails,
            'Meeting': instance_id.is_meetings,
            'To-Do': instance_id.is_tasks
        }
        return activity_type_mapping.get(activity_type.name, False)

    # ----------  Create or update a Pipedrive activity based on an Odoo activity ---------- #
    @api.model
    def create_or_update_pipedrive_activity(self, api_token, odoo_activity, operation_type):
        """
                Create or update a Pipedrive activity based on an Odoo activity.

                Args:
                    instance_id (object): Instance of the Pipedrive configuration.
                    api_token (str): Pipedrive API token.
                    odoo_activity (object): Odoo activity object.

                Returns:
                    None
        """
        # Extract relevant data from the Odoo activity
        try:
            activity_type = odoo_activity.activity_type_id
            due_date = odoo_activity.date_deadline
            note = odoo_activity.summary
            odoo_record = self.env[odoo_activity.res_model].browse(odoo_activity.res_id)
            activity_user_id = odoo_activity.user_id.pipedrive_id
            activity_id = odoo_activity.pipedrive_activity_id
            odoo_activity_user_id = odoo_activity.user_id.id
            pipedrive_activity_user = self.env['res.users'].search([('pipedrive_id', '=', activity_user_id)], limit=1)
            pipedrive_activity_user_id = pipedrive_activity_user.id
            # Check if the record is a company or contact
            record_type = self.get_record_type(odoo_record)

            pipedrive_activity_type = self.get_pipedrive_activity_type(activity_type)

            due_date_str = due_date.strftime('%Y-%m-%d')
            # Prepare data for Pipedrive activity
            pipedrive_activity_data = {
                'type': pipedrive_activity_type,
                'due_date': due_date_str,
                'user_id': int(activity_user_id),
                'note': note,
                'org_id': odoo_record.pipedrive_id if record_type == 'organization' else None,
                'person_id': odoo_record.pipedrive_id if record_type == 'person' else None,
                'lead_id': odoo_record.pipedrive_id if record_type == 'lead' else None,
                'deal_id': odoo_record.pipedrive_id if record_type == 'deal' else None,
            }

            # Check if the Odoo activity already has a Pipedrive ID
            activity_id_value = self.env['opd.mapper.mixin'].get_update_time_field('opd.activitymapper', 'id')
            filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, activity_id, activity_id_value, 'activity',
                                                                   'activity', 'activity', operation_type)
            endpoint = f'{self.__API_BASE_URL}activities?user_id=0&filter_id={filter_id}&api_token={api_token}'
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            payload_rec = {}

            # Make a GET request to the API endpoint
            response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")
            if response.status_code != 200:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch odoo activity filter ID"
                self.env['opd.mapper.mixin'].http_log_error(error_details, 'activity', description, {}, response.text, 'pipedrive', operation_type, '', f"HTTP {response.status_code}")

            response_json = response.json()
            pipedrive_record = response_json.get('data', [])

            if pipedrive_record is not None:
                # Create new activity in Pipedrive
                pipedrive_record_id = pipedrive_record[0]['id'] if isinstance(pipedrive_record, list) else pipedrive_record['id']

                if pipedrive_activity_user_id == odoo_activity_user_id:
                    pipedrive_activity_data.pop('owner_id', None)
                else:
                    pipedrive_activity_data = pipedrive_activity_data
                # Convert the data to JSON format
                json_data = json.dumps(pipedrive_activity_data)

                update_endpoint = f'{self.__API_BASE_URL}activities/{pipedrive_record_id}?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = requests.request("PUT", update_endpoint, headers=headers, data=json_data)
                if response.status_code == 200:
                    response_json = response.json()
                    record = response_json.get('data', [])
                    pipedrive_id = record.get('id')
                    self.env['opd.mapper.mixin'].log_operation('activity', response.status_code, pipedrive_id, json_data, 'update',
                                                               'pipedrive', operation_type,
                                                               parent_name=None,
                                                               parent_id=None)
                    odoo_activity.write({'pipedrive_activity_id': pipedrive_id})
                    odoo_activity.env.cr.commit()
                else:
                    error_details = f"{response.status_code} - {response.reason}"
                    description = f"Failed to update pipedrive activity"
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'activity', description, json_data,
                                                                response.text, 'pipedrive', operation_type, '', f"HTTP {response.status_code}")

            else:
                # Create new activity in Pipedrive
                create_endpoint = f'{self.__API_BASE_URL}activities?api_token={api_token}'
                # Convert the data to JSON format
                json_data = json.dumps(pipedrive_activity_data)
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, json_data,
                                                                   method="POST")
                if response.status_code in [200, 201]:
                    response_json = response.json()
                    record = response_json.get('data', [])
                    pipedrive_id = record.get('id')
                    self.env['opd.mapper.mixin'].log_operation('activity', response.status_code, pipedrive_id, json_data, 'create', 'pipedrive', operation_type,
                                                               parent_name=None,
                                                               parent_id=None)
                    odoo_activity.write({'pipedrive_activity_id': pipedrive_id})
                    odoo_activity.env.cr.commit()
                else:
                    error_details = f"{response.status_code} - {response.reason}"
                    description = f"Failed to create pipedrive activity"
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'activity', description, json_data, response.text, 'pipedrive', operation_type, '', f"HTTP {response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create/update activity'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'activity', description, 'pipedrive', operation_type, '', error_type)

    # ------------- Create or update a Pipedrive note based on an Odoo note. -------------- #
    def create_or_update_pipedrive_notes(self, api_token, odoo_note, operation_type):
        """
                  Create or update a Pipedrive note based on an Odoo note.

                  Args:
                      api_token (str): Pipedrive API token.
                      odoo_note (object): Odoo note object.

                  Returns:
                      None
                    instance_id:
            """
        try:
            # Extract relevant data from the Odoo Notes
            pipedrive_notes_id = odoo_note.pipedrive_notes_id
            body = odoo_note['body'],
            odoo_record = self.env[odoo_note.model].browse(odoo_note.res_id)
            # Check if the record is a company or contact
            record_type = self.get_record_type(odoo_record)

            pipedrive_notes_data = {
                'content': body[0],
                'org_id': odoo_record.pipedrive_id if record_type == 'organization' else None,
                'person_id': odoo_record.pipedrive_id if record_type == 'person' else None,
                'lead_id': odoo_record.pipedrive_id if record_type == 'lead' else None,
                'deal_id': odoo_record.pipedrive_id if record_type == 'deal' else None,
            }

            # Convert the data to JSON format
            json_data = json.dumps(pipedrive_notes_data)

            # Check if the Odoo note already has a Pipedrive ID
            if pipedrive_notes_id:
                # Update existing activity in Pipedrive
                update_endpoint = f'{self.__API_BASE_URL}notes/{pipedrive_notes_id}?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = requests.request("PUT", update_endpoint, headers=headers,
                                            data=json_data)

                if not response.status_code == 200:
                    error_details = f"{response.status_code} - {response.reason}"
                    description = f"Failed to update pipedrive notes"
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'note', description, json_data, response.text, 'pipedrive', operation_type, '', f"HTTP {response.status_code}")
                else:
                    self.env['opd.mapper.mixin'].log_operation('note', response.status_code, pipedrive_notes_id, json_data,
                    'update', 'pipedrive', operation_type,parent_name=None, parent_id=None)
            else:
                # Create new note in Pipedrive
                create_endpoint = f'{self.__API_BASE_URL}notes?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, json_data,
                                                                   method="POST")
                if response.status_code in [200, 201]:
                    response_json = response.json()
                    record = response_json.get('data', [])
                    pipedrive_id = record.get('id')
                    self.env['opd.mapper.mixin'].log_operation('note', response.status_code, pipedrive_id, json_data, 'create', 'pipedrive', operation_type,
                                                               parent_name=None,
                                                               parent_id=None)
                    odoo_note.write({'pipedrive_notes_id': pipedrive_id})
                    odoo_note.env.cr.commit()
                else:
                    error_details = f"{response.status_code} - {response.reason}"
                    description = f"Failed to create pipedrive notes"
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'note', description, json_data, response.text, 'pipedrive', operation_type, '',  f"HTTP {response.status_code}")
        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create/update notes'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'note', description, 'pipedrive', operation_type, '', error_type)


class MailMessageInherit(models.Model):
    """
        This class inherits the 'mail.message' model and adds additional field for fetching pipedrive Notes ID.

       """
    _inherit = 'mail.message'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_notes_id = fields.Char(string='Pipedrive Note ID', readonly=True)
    pipedrive_email_id = fields.Char(string='Pipedrive Email ID', readonly=True)

class IrAttachmentInherit(models.Model):
    """
        This class inherits the 'ir.attachment' model and adds additional field for fetching pipedrive Notes ID.

       """
    _inherit = 'ir.attachment'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_attachment_id = fields.Char(string='Pipedrive Attachment ID', readonly=True)
