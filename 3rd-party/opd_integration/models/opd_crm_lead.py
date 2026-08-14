# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
from datetime import date, datetime
import json
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResCrmLeadInherit(models.Model):
    """
       Description:
           This class inherits the 'crm.lead' model and adds additional functionality for fetching
           crm data from Pipedrive and updating records in Odoo.

       """
    _inherit = 'crm.lead'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_id = fields.Char(string='Pipedrive ID')
    sync_to_pipedrive = fields.Selection([
        ('yes', 'Yes'),('no', 'No'),], string='Sync To Pipedrive', default='yes')
    odoo_hash = fields.Char(string='Odoo hash')

    @api.model
    def fetch_lead_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches lead data from Pipedrive and updates records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive Lead Last Sync Date.
        #        """
        odoo_model_name = 'crm.lead'  # Define the Odoo model name
        return self.env['opd.mapper.mixin'].fetch_crm_data_from_pipedrive(instance_id, 'leads',
               odoo_model_name,'pipedriveinstance.leads.lines','opd.leadmapper', last_sync_date,
              'is_lead_calls', 'is_lead_tasks','is_lead_emails', 'is_lead_meetings','is_lead_notes',
              'leads', 'lead','pipedrive_lead_dropdown_mapping','lead', 'lead', operation_type)

    @api.model
    def fetch_deal_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches deal data from Pipedrive and updates records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive Deal Last Sync Date.
        #        """
        odoo_model_name = 'crm.lead'  # Define the Odoo model name
        return self.env['opd.mapper.mixin'].fetch_crm_data_from_pipedrive(instance_id, 'deals',
               odoo_model_name,'pipedriveinstance.deals.lines','opd.dealmapper', last_sync_date,
               'is_deal_calls', 'is_deal_tasks','is_deal_emails','is_deal_meetings','is_deal_notes',
               'deals', 'deal','pipedrive_deal_dropdown_mapping','opportunity', 'deal', operation_type)

    @api.model
    def fetch_lead_from_odoo(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches lead data from Odoo and updates records in Pipedrive.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Odoo Lead Last Sync Date.
        #        """
        return self.fetch_all_odoo_crm_data(instance_id, 'crm.lead', 'lead', last_sync_date,
                                            'leads', 'pipedriveinstance.leads.lines',
                                            'opd.leadmapper', 'leads', 'lead',
                                            'odoo_lead_dropdown_mapping', 'lead', operation_type)

    @api.model
    def fetch_deal_from_odoo(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches deal data from Odoo and updates records in Pipedrive.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Odoo Deal Last Sync Date.
        #        """
        return self.fetch_all_odoo_crm_data(instance_id, 'crm.lead', 'opportunity', last_sync_date,
               'deals', 'pipedriveinstance.deals.lines',
               'opd.dealmapper', 'deals', 'deal', 'odoo_deal_dropdown_mapping', 'deal', operation_type)

    # ------------------------- Fetch Odoo CRM Data and Transfer to Pipedrive ---------------- #

    def fetch_all_odoo_crm_data(self, instance_id, model_name, crm_type, last_sync_date_field, pipedrive_model_name,
                                field_model_name, field_mapper_model, type, object, dropdown_mapping_field,
                                logger_name, operation_type):
        """
        Transfer data from Odoo to Pipedrive for all companies.

        Args:
            instance_id: The Pipedrive instance ID.
            model_name: The name of the Odoo model containing company data.
            crm_type: The type of CRM record ('lead' or 'opportunity').
            last_sync_date_field: The field indicating the last synchronization date.
            pipedrive_model_name: The name of the Pipedrive model for companies.
            field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
            field_id: The ID of the field.
            type: The type of the field.
            object: The object type.
            dropdown_mapping_field: The name of the field in `instance_id` containing dropdown mapping information.

        Returns:
            None
        """

        try:

            limit, offset = self.env['opd.mapper.mixin'].initialize_pagination(instance_id, logger_name, 'pipedrive', operation_type)

            if limit == 0:
                return
            # Set a temporary variable to store the current UTC time at the start of the function
            last_sync_date, current_utc_time = self.env['opd.mapper.mixin'].last_sync_date_common(last_sync_date_field)

            if crm_type == 'lead':
                record_last_id = instance_id.odoo_lead_last_id
            else:
                record_last_id = instance_id.odoo_deal_last_id

            api_token = instance_id.api_token if 'api_token' in instance_id else None
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            while True:
                additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'write_date', 'partner_id',
                                     'sync_to_pipedrive', 'tag_ids']
                crm_records = self.env['opd.mapper.mixin'].fetch_odoo_records(
                field_model_name, instance_id, model_name,additional_fields, record_last_id, logger_name, operation_type,
                is_company=None, crm_type=crm_type,last_sync_date=last_sync_date, offset=0, limit=limit)

                if not crm_records:
                    break

                for crm_record in crm_records:
                    result, pipedrive_id = self.process_crm_odoo_record(instance_id, crm_record, crm_type, model_name,
                    pipedrive_model_name,field_model_name, field_mapper_model, type,object, dropdown_mapping_field,
                    headers,api_token, logger_name, operation_type, check_hash=True)

                    if pipedrive_id and result != 'no_update':
                        self.process_activities_and_notes(instance_id, crm_record, crm_type, model_name, api_token, operation_type,
                                                          is_activity=True)
                    else:
                        continue

                record_last_id = crm_records[-1].get('id') if isinstance(crm_records[-1],
                                                                         dict) else crm_records[-1].id
                if crm_type == 'lead':
                    instance_id.write({'odoo_lead_last_id': record_last_id})
                else:
                    instance_id.write({'odoo_deal_last_id': record_last_id})

                instance_id.env.cr.commit()

                if len(crm_records) < limit:
                    break

            if crm_type == 'lead':
                instance_id.write({'odoo_lead_last_sync_date': current_utc_time})
                instance_id.write({'odoo_lead_last_id': 0})
            elif crm_type == 'opportunity':
                instance_id.write({'odoo_deal_last_sync_date': current_utc_time})
                instance_id.write({'odoo_deal_last_id': 0})
            self.env['opd.mapper.mixin'].scheduler_run_successfully_log(logger_name, operation_type, 'pipedrive')
        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, '',
                                                             error_type)

    # ----------------------------- Process A Single Odoo Record ----------------------------- #
    def process_crm_odoo_record(self, instance_id, odoo_record, crm_type, model_name, pipedrive_model_name,
                                field_model_name, field_mapper_model, type, object, dropdown_mapping_field, headers,
                                api_token, logger_name, operation_type, check_hash=True):
        """
        Process a single Odoo record.

        Args:
            instance_id (int): The Pipedrive instance ID.
            odoo_record (dict): The Odoo record to process.
            crm_type (str): The type of CRM record ('lead' or 'opportunity').
            model_name (str): The name of the Odoo model containing company data.
            pipedrive_model_name (str): The name of the Pipedrive model for companies.
            field_model_name (str): The name of the model containing field mappings between Pipedrive and Odoo.
            field_mapper_model (int): The ID of the field.
            type (str): The type of the field.
            object (str): The object type.
            dropdown_mapping_field (str): The name of the field in `instance_id` containing dropdown mapping information.
            headers (dict): The headers for the API requests.
            api_token (str): The API token for Pipedrive.
            logger_name (str): The name of the logger.
            check_hash(Bool): Check Odoo Hash based on Check hash True or False
        Returns:
            tuple: (Processed record data or None, Error message or None)
        """
        odoo_id = None
        try:
            odoo_id = odoo_record.get('id') if isinstance(odoo_record, dict) else odoo_record.id
            # Map Odoo fields to Pipedrive fields
            crm_record_data, dynamic_fields_values_hash, operation_status = self.env[
                'opd.mapper.mixin'].odoo_to_pipedrive_map_fields(
                odoo_record, instance_id, field_model_name, dropdown_mapping_field, odoo_id, logger_name, operation_type)
            if operation_status == 'skip':
                return None, None

            if crm_record_data:
                # Retrieve partner record and organization ID from the Odoo record
                partner_record = odoo_record.get('partner_id') if isinstance(odoo_record,
                                                                             dict) else odoo_record.partner_id

                partner_obj, org_id, sync_to_pipedrive, partner_id = None, None, None, None

                if isinstance(partner_record, tuple):
                    # Assuming the first element of the tuple is the ID and the second element is the name
                    partner_id = partner_record[0]
                    partner_obj = self.env['res.partner'].browse(partner_id)
                elif partner_record:
                    partner_obj = partner_record
                    partner_id = partner_record.id

                if partner_obj:
                    org_id = partner_obj.pipedrive_id
                    sync_to_pipedrive = partner_obj.sync_to_pipedrive

                if not partner_obj:
                    description = f"Partner id is required for {logger_name} send odoo to pipedrive, {logger_name} ID: {odoo_id}"
                    operation = f'create/update {logger_name}'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, description, operation, 'pipedrive',
                                                                       crm_record_data, operation_type, odoo_id)
                    return None, None

                # Process the Pipedrive record based on the partner record information
                if org_id and sync_to_pipedrive == 'yes':
                    return self.update_or_create_pipedrive_crm_record(instance_id,
                        odoo_record, partner_obj, crm_type, pipedrive_model_name, headers, api_token, crm_record_data,
                        dynamic_fields_values_hash, org_id, field_mapper_model, type, object, logger_name, operation_type, check_hash)
                elif sync_to_pipedrive == 'yes':
                    if partner_obj.is_company:
                        return self.process_crm_company(
                            partner_obj, odoo_record, instance_id, api_token, headers, crm_type, model_name,
                            pipedrive_model_name,
                            crm_record_data, dynamic_fields_values_hash, field_mapper_model, type, object, logger_name, operation_type,
                            check_hash)
                    else:
                        return self.process_crm_contact(
                            partner_obj, odoo_record, instance_id, api_token, headers, crm_type, pipedrive_model_name,
                            crm_record_data, dynamic_fields_values_hash, field_mapper_model, type, object, logger_name, operation_type,
                            check_hash)
                else:
                    description = (f'Sync to Pipedrive is required to be "Yes" for {logger_name.capitalize()} related '
                                   f'Partner ID {partner_id}.')
                    operation = f'create/update {logger_name}'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, description, operation, 'pipedrive',
                                                                       crm_record_data, operation_type, odoo_id)
                    return None, None
            else:
                return None, None

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f"Error occurred while {logger_name} create/update in pipedrive."
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, odoo_id,
                                                             error_type)
            return None, None

    # ------------------------- Send Odoo Activities and Notes to Pipedrive -------------- #
    def process_activities_and_notes(self, instance_id, odoo_record, crm_type, model_name, api_token, operation_type, is_activity=True):
        """
        Process activities and notes for an Odoo record.

        Args:
            instance_id: The Pipedrive instance ID.
            odoo_record: The Odoo record to process.
            crm_type: The type of CRM record ('lead' or 'opportunity').
            model_name: The name of the Odoo model containing company data.
            api_token: The API token for Pipedrive.

        Returns:
            None
        """
        odoo_id = odoo_record.get('id') if isinstance(odoo_record, dict) else odoo_record.id
        odoo_crm_activities = self.env['mail.activity'].search(
            [('res_id', '=', odoo_id), ('res_model', '=', model_name), ('active', '=', True)])
        odoo_crm_notes = self.env['mail.message'].search(
            [('res_id', '=', odoo_id), ('model', '=', model_name), ('message_type', '=', 'comment')])

        if crm_type == 'lead':
            last_sync_date = instance_id.odoo_lead_last_sync_date
        else:
            last_sync_date = instance_id.odoo_deal_last_sync_date

        if odoo_crm_activities:
            for odoo_activity in odoo_crm_activities:
                activity_update_time = odoo_activity.get('write_date') if isinstance(odoo_activity,
                                                                                     dict) else odoo_activity.write_date
                if activity_update_time > last_sync_date or not is_activity:
                    activity_type = odoo_activity.get('activity_type_id') if isinstance(odoo_activity,
                                                                                        dict) else odoo_activity.activity_type_id
                    activity_type_id = activity_type.get('id') if isinstance(activity_type, dict) else activity_type.id
                    if self.env['opd.mapper.mixin'].should_process_crm_activity(instance_id, crm_type,
                                                                                activity_type_id):
                        self.env['mail.activity'].create_or_update_pipedrive_activity(api_token, odoo_activity, operation_type)

        if (instance_id.is_lead_notes and crm_type == 'lead') or (
                instance_id.is_deal_notes and crm_type == 'opportunity'):
            for odoo_note in odoo_crm_notes:
                note_update_time = odoo_note.get('write_date') if isinstance(odoo_note,
                                                                             dict) else odoo_note.write_date
                if note_update_time > last_sync_date or not is_activity:
                    self.env['mail.activity'].create_or_update_pipedrive_notes(api_token, odoo_note, operation_type)

    # ------------------------ Create And Update CRM Related Company And Send to Pipedrive ---------------- #

    def process_crm_company(self, company, odoo_record, instance_id, api_token, headers, crm_type, model_name,
        pipedrive_model_name,crm_record_data, dynamic_fields_values_hash, field_mapper_model, type, object, logger_name,
        operation_type,check_hash):
        """
            Processes a company record from Odoo and sends it to Pipedrive for creation or updating.

            This function maps the fields from the Odoo company record to the Pipedrive format, sends a request to
            create the company in Pipedrive, and updates the Odoo record with the Pipedrive ID and hash. It then
            calls a function to update or create the related CRM record in Pipedrive.

            Parameters:
                company (recordset): The Odoo company record to be processed.
                odoo_record (recordset): The related Odoo CRM record (lead or opportunity).
                instance_id (recordset): The Pipedrive instance configuration.
                api_token (str): The API token for authenticating with Pipedrive.
                headers (dict): The headers for the API request.
                crm_type (str): The type of CRM record ('lead' or 'opportunity').
                model_name (str): The name of the Odoo model.
                pipedrive_model_name (str): The model name in Pipedrive.
                crm_record_data (dict): The CRM record data to be sent to Pipedrive.
                dynamic_fields_values_hash (str): The hash value of the dynamic fields to check for changes.
                field_id (int): The field ID to be used in the Pipedrive record.
                type (str): The type of the record.
                object (str): The object type being processed.
                logger_name (str): The name of the logger to use for logging operations.
                check_hash(Bool): Check Odoo Hash based on Check hash True or False
            Returns:
                str: 'create' or 'update' indicating the action taken in Pipedrive, or None if an error occurred.
        """

        odoo_record_id = company.get('id') if isinstance(company, dict) else company.id
        record_data, partner_dynamic_fields_values_hash, operation_status = self.env[
            'opd.mapper.mixin'].odoo_to_pipedrive_map_fields(
            company, instance_id, 'pipedriveinstance.companies.lines', 'odoo_company_dropdown_mapping', odoo_record_id,
            'company', operation_type)
        record_data = self.env['opd.mapper.mixin'].build_pipedrive_v2_payload(record_data, 'company')
        if operation_status == 'skip':
            return None, None

        if record_data:
            sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.companymapper', 'odoo_id',
                                                    field_name='internal_name')
            # Ensure custom_fields exists
            if "custom_fields" not in record_data or not isinstance(record_data["custom_fields"],
                                                                        dict):
                record_data["custom_fields"] = {}

            # Merge new value instead of replacing the entire dict
            record_data["custom_fields"][sync_field] = str(odoo_record_id)

            create_endpoint = f"{instance_id.api_base_url}/organizations?api_token={api_token}"
            create_payload = json.dumps(record_data)
            response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, create_payload, method="POST")

            if response.status_code in [200, 201]:
                response_json = response.json()
                pipedrive_record_id = response_json.get('data', {}).get('id')
                company.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': partner_dynamic_fields_values_hash})
                company.env.cr.commit()
                self.env['opd.mapper.mixin'].log_operation('company', response.status_code, odoo_record_id,
                         record_data, 'create','pipedrive', operation_type, parent_name=None,
                         parent_id=None)
                result, pipedrive_record_id = self.update_or_create_pipedrive_crm_record(instance_id, odoo_record, company, crm_type,
                pipedrive_model_name,headers,api_token, crm_record_data,dynamic_fields_values_hash, pipedrive_record_id,
                field_mapper_model, type, object,logger_name, operation_type, check_hash)
                return result, pipedrive_record_id
            else:
                self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", 'company',
                                                            f"Failed to create company in pipedrive", record_data,
                                                            response.text, 'pipedrive', operation_type, odoo_record_id,
                                                            f"HTTP {response.status_code}")
                return None, None
        else:
            return None, None

    # ------------------------ Create And Update CRM Related Contact And Send to Pipedrive ---------------- #

    def process_crm_contact(self, contact, odoo_record, instance_id, api_token, headers, crm_type,
        pipedrive_model_name,crm_record_data, dynamic_fields_values_hash, field_mapper_model, type, object, logger_name, operation_type,
        check_hash):
        """
            Processes a contact record from Odoo and sends it to Pipedrive for creation or updating.

            This function maps the fields from the Odoo contact record to the Pipedrive format, sends a request to
            create the contact in Pipedrive, and updates the Odoo record with the Pipedrive ID and hash. It then
            calls a function to update or create the related CRM record in Pipedrive.

            Parameters:
                contact (recordset): The Odoo contact record to be processed.
                odoo_record (recordset): The related Odoo CRM record (lead or opportunity).
                instance_id (recordset): The Pipedrive instance configuration.
                api_token (str): The API token for authenticating with Pipedrive.
                headers (dict): The headers for the API request.
                crm_type (str): The type of CRM record ('lead' or 'opportunity').
                model_name (str): The name of the Odoo model.
                pipedrive_model_name (str): The model name in Pipedrive.
                crm_record_data (dict): The CRM record data to be sent to Pipedrive.
                dynamic_fields_values_hash (str): The hash value of the dynamic fields to check for changes.
                field_id (int): The field ID to be used in the Pipedrive record.
                type (str): The type of the record.
                object (str): The object type being processed.
                logger_name (str): The name of the logger to use for logging operations.
                check_hash(Bool): Check Odoo Hash based on Check hash True or False
            Returns:
                str: 'create' or 'update' indicating the action taken in Pipedrive, or None if an error occurred.
        """
        odoo_record_id = contact.get('id') if isinstance(contact, dict) else contact.id
        record_data, partner_dynamic_fields_values_hash, operation_status = self.env['opd.mapper.mixin'].odoo_to_pipedrive_map_fields(
            contact, instance_id, 'pipedriveinstance.contacts.lines', 'odoo_contacts_dropdown_mapping', odoo_record_id,
            'contact', operation_type)
        record_data = self.env['opd.mapper.mixin'].build_pipedrive_v2_contact_payload(record_data)
        if operation_status == 'skip':
            return None, None

        if record_data:
            sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.contactmapper', 'odoo_id',
                                                    field_name='internal_name')

            # Ensure custom_fields exists
            if "custom_fields" not in record_data or not isinstance(record_data["custom_fields"],
                                                                    dict):
                record_data["custom_fields"] = {}

            # Merge new value instead of replacing the entire dict
            record_data["custom_fields"][sync_field] = str(odoo_record_id)
            contact_email = contact.get('email') if isinstance(contact, dict) else contact.email
            email_id_value = self.env['opd.mapper.mixin'].get_update_time_field('opd.contactmapper', 'email')
            record = self.env['opd.contactmapper'].search([('label_name', '=', 'odoo_id')], limit=1)
            if record:
                # Accessing the first record in the recordset
                record_field_name = record.internal_name
            else:
                # Handling the case where no record is found
                record_field_name = None

            if contact_email:
                filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, contact_email, email_id_value, 'people',
                                                                       'person', logger_name, operation_type)
                if filter_id:
                    # Fetch the record using the filter_id to check the odoo_id
                    endpoint = f'{instance_id.api_base_url}/persons?filter_id={filter_id}&api_token={api_token}'
                    pipedrive_record, status_code = self.env['opd.mapper.mixin'].update_or_create_pipedrive_record({},
                                                    endpoint,headers,logger_name, operation_type,method='GET')
                    if pipedrive_record:
                        existing_odoo_id = pipedrive_record[0].get(record_field_name) if isinstance(pipedrive_record,
                                                                                                    list) else pipedrive_record.get(
                            record_field_name)
                        if existing_odoo_id:
                            description = f'The email ID {contact_email} is already associated with another contact. Please use a different email ID. As a result, the associated lead or opportunity will not be created without a valid partner record.'
                            operation = f'{logger_name} Related Contact Send Odoo To Pipedrive'
                            self.env['opd.mapper.mixin'].log_operation_warning(logger_name, description, operation,
                                                                               'pipedrive', pipedrive_record, operation_type, odoo_record_id)
                            return None, None

            # If no existing contact found, create a new one
            self.env['res.users'].set_record_data(contact, 'user_id', 'owner_id', record_data)
            create_endpoint = f"{instance_id.api_base_url}/persons?api_token={api_token}"
            create_payload = json.dumps(record_data)
            response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, create_payload, method="POST")

            if response.status_code in [200, 201]:
                response_json = response.json()
                pipedrive_record_id = response_json.get('data', {}).get('id')
                contact.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': partner_dynamic_fields_values_hash})
                contact.env.cr.commit()
                self.env['opd.mapper.mixin'].log_operation('contact', response.status_code, odoo_record_id,
                        create_payload, 'create','pipedrive', operation_type, parent_name=None,
                        parent_id=None)
                result, pipedrive_record_id = self.update_or_create_pipedrive_crm_record(instance_id, odoo_record, contact, crm_type,
                                              pipedrive_model_name,headers,api_token, crm_record_data,
                                              dynamic_fields_values_hash,pipedrive_record_id,field_mapper_model, type,
                                              object,logger_name, operation_type, check_hash)
                return result, pipedrive_record_id
            else:
                self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", 'contact',
                                                            f"Failed to create contact in pipedrive", record_data,
                                                            response.text, 'pipedrive', operation_type, odoo_record_id,
                                                            f"HTTP {response.status_code}")
                return None, None
        else:
            return None, None

    # -------------------------- Create and Update Pipedrive Lead and Deal ---------------------- #
    def update_or_create_pipedrive_crm_record(self, instance_id, odoo_record, partner_record, crm_type, pipedrive_model_name,
         headers,api_token, crm_record_data, dynamic_fields_values_hash, org_id, field_mapper_model,
         type, object, logger_name, operation_type, check_hash):
        """
        Update or create a record in Pipedrive.

        Args:
            instance_id: The Pipedrive instance ID.
            odoo_record: The Odoo record to process.
            crm_type: The type of CRM record ('lead' or 'opportunity').
            pipedrive_model_name: The name of the Pipedrive model for companies.
            headers: The headers for the API requests.
            api_token: The API token for Pipedrive.
            now_utc: The current UTC time.
            crm_record_data: The CRM record data.
            dynamic_fields_values_hash: The hash of dynamic field values.
            org_id: The organization ID in Pipedrive.
            check_hash(Bool): Check Odoo Hash based on Check hash True or False
        Returns:
            None
        """
        odoo_id = odoo_record.get('id') if isinstance(odoo_record, dict) else odoo_record.id
        crm_pipedrive_id = odoo_record.get('pipedrive_id') if isinstance(odoo_record, dict) else odoo_record.pipedrive_id
        if partner_record.is_company:
            if crm_type == 'lead' and org_id:
                crm_record_data['organization_id'] = int(org_id)
            elif crm_type == 'opportunity' and org_id:
                crm_record_data['org_id'] = int(org_id)
        else:
            if crm_type == 'lead' and org_id:
                crm_record_data['person_id'] = int(org_id)
            elif crm_type == 'opportunity' and org_id:
                crm_record_data['person_id'] = int(org_id)

        if crm_type == 'lead':
            odoo_user_id = self.env['res.users'].set_record_data(odoo_record, 'user_id', 'owner_id', crm_record_data)
            sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.leadmapper', 'odoo_id',
                                                                            field_name='internal_name')
            crm_record_data[sync_field] = str(odoo_id)
            crm_endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'
        else:
            odoo_user_id = self.env['res.users'].set_record_data(odoo_record, 'user_id', 'owner_id', crm_record_data)
            sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.dealmapper', 'odoo_id',
                                                                            field_name='internal_name')
            # Ensure custom_fields exists
            if "custom_fields" not in crm_record_data or not isinstance(crm_record_data["custom_fields"], dict):
                crm_record_data["custom_fields"] = {}

            # Merge new value instead of replacing the entire dict
            crm_record_data["custom_fields"][sync_field] = str(odoo_id)
            crm_endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'

        if crm_record_data:
            if crm_pipedrive_id:
                payload_rec = {}
                response = self.env['opd.mapper.mixin'].fetch_data(crm_endpoint, headers, payload_rec, method="GET")
                if response.status_code != 200:
                    self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", 'lead',
                                                                f"Failed to fetch pipedrive record", payload_rec,
                                                                response.text, 'pipedrive', operation_type, odoo_id,
                                                                f"HTTP {response.status_code}")
                    return None, None

                response_json = response.json()
                pipedrive_record = response_json.get('data', [])
                if pipedrive_record:
                    pipedrive_id = pipedrive_record[0]['id'] if isinstance(pipedrive_record, list) else pipedrive_record['id']
                    odoo_hash = odoo_record.get('odoo_hash') if isinstance(odoo_record, dict) else odoo_record.odoo_hash
                    if not check_hash or odoo_hash != dynamic_fields_values_hash:
                        result, pipedrive_id = self.update_pipedrive_record(instance_id, crm_type, pipedrive_model_name, headers, api_token,
                                               crm_record_data,dynamic_fields_values_hash, pipedrive_id,odoo_id, logger_name,
                                               odoo_user_id,pipedrive_record, operation_type)
                        return result, pipedrive_id
                    else:
                        return 'no_update', pipedrive_id
                else:
                    return None, None
            else:
                result, pipedrive_id = self.create_pipedrive_record(instance_id, pipedrive_model_name, headers, api_token,
                              crm_record_data,odoo_id, dynamic_fields_values_hash, logger_name, operation_type)
                return result, pipedrive_id
        else:
            return None, None

    # ----------------------- Update Pipedrive Lead and Deal ---------------- #

    def update_pipedrive_record(self, instance_id, crm_type, pipedrive_model_name, headers, api_token, crm_record_data,
                                dynamic_fields_values_hash, pipedrive_id, odoo_id, logger_name, odoo_user_id,
                                pipedrive_record, operation_type):
        """
        Update a record in Pipedrive.

        Args:
            crm_type: The type of CRM record ('lead' or 'opportunity').
            pipedrive_model_name: The name of the Pipedrive model for companies.
            headers: The headers for the API requests.
            api_token: The API token for Pipedrive.
            crm_record_data: The CRM record data.
            dynamic_fields_values_hash: The hash of dynamic field values.
            pipedrive_id: The Pipedrive record ID.
            odoo_id: The Odoo record ID.

        Returns:
            None
        """
        pipedrive_source = pipedrive_record[0] if isinstance(pipedrive_record, list) else pipedrive_record
        user_record = self.env['opd.mapper.mixin'].get_odoo_user_from_pipedrive_record(pipedrive_source)
        if crm_type == 'opportunity':
            if "probability" in crm_record_data and crm_record_data["probability"] not in (None, ""):
                crm_record_data["probability"] = int(round(float(crm_record_data["probability"])))
            if "stage_id" in crm_record_data and crm_record_data["stage_id"]:
                crm_record_data["stage_id"] = int(crm_record_data["stage_id"])
        pipedrive_user_id = user_record.id if user_record else None
        if odoo_user_id == pipedrive_user_id:
            crm_record_data.pop('owner_id', None)

        if 'expected_close_date' in crm_record_data:
            if crm_record_data['expected_close_date']:
                crm_record_data['expected_close_date'] = crm_record_data['expected_close_date'].isoformat()
            else:
                crm_record_data['expected_close_date'] = ''

        update_payload = json.dumps(crm_record_data, default=self.custom_serializer)
        crm_record = self.env['crm.lead'].browse(odoo_id)
        crm_record.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
        crm_record.env.cr.commit()
        response = None
        if crm_type == 'lead':
            update_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}/{pipedrive_id}?api_token={api_token}"
            response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)

        elif crm_type == 'opportunity':
            update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_id}?api_token={api_token}"
            response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)

        if response.status_code != 200:
            self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", logger_name,
                                                        f"Failed to update {logger_name} in pipedrive", crm_record_data,
                                                        response.text, 'pipedrive', operation_type, odoo_id,
                                                        f"HTTP {response.status_code}")
            return None, None
        else:
            self.env['opd.mapper.mixin'].log_operation(logger_name, response.status_code, odoo_id, crm_record_data,
                            'update','pipedrive', operation_type, parent_name=None,parent_id=None)
            return 'update', pipedrive_id

    # ----------------------- Create Pipedrive Lead and Deal ---------------- #
    def create_pipedrive_record(self, instance_id, pipedrive_model_name, headers, api_token, crm_record_data, odoo_id,
                                dynamic_fields_values_hash, logger_name, operation_type):
        """
        Create a record in Pipedrive.

        Args:
            crm_type: The type of CRM record ('lead' or 'opportunity').
            pipedrive_model_name: The name of the Pipedrive model for companies.
            headers: The headers for the API requests.
            api_token: The API token for Pipedrive.
            crm_record_data: The CRM record data.
            odoo_id: The Odoo record ID.
            dynamic_fields_values_hash: The hash of dynamic field values.

        Returns:
            None
        """

        if 'expected_close_date' in crm_record_data and crm_record_data['expected_close_date']:
            crm_record_data['expected_close_date'] = crm_record_data['expected_close_date'].isoformat()
        else:
            if pipedrive_model_name == 'deals':
                crm_record_data['expected_close_date'] = ''

        # -------- DEAL SPECIFIC FIXES --------
        if logger_name == "deal":

            # probability must be INT
            if "probability" in crm_record_data and crm_record_data["probability"] not in (None, ""):
                crm_record_data["probability"] = int(round(float(crm_record_data["probability"])))

            # stage_id must be INT
            if "stage_id" in crm_record_data and crm_record_data["stage_id"]:
                crm_record_data["stage_id"] = int(crm_record_data["stage_id"])

        create_payload = json.dumps(crm_record_data, default=self.custom_serializer)
        if logger_name == 'deal':
            create_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}"
        else:
            create_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}?api_token={api_token}"

        response = requests.request("POST", create_endpoint, headers=headers, data=create_payload)

        if response.status_code in [200, 201]:
            response_data = response.json()
            pipedrive_id = response_data.get('data', {}).get('id')
            crm_record = self.env['crm.lead'].browse(odoo_id)
            crm_record.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
            crm_record.env.cr.commit()
            self.env['opd.mapper.mixin'].log_operation(logger_name, response.status_code, odoo_id, create_payload,
            'create','pipedrive', operation_type, parent_name=None, parent_id=None)

            return 'create', pipedrive_id
        else:
            self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", logger_name,
                                                        f"Failed to create {logger_name} in pipedrive", crm_record_data,
                                                        response.text, 'pipedrive', operation_type, odoo_id,
                                                        f"HTTP {response.status_code}")
            return None, None

    # ------------------------------ Send Record To Pipedrive From CRM Form and Tree View ------------------------- #

    def crm_record_send_to_pipedrive(self):
        """
            Sends records from Odoo to Pipedrive. Handles both leads and opportunities, and logs the process.

            This function processes active records in the current context and sends them to Pipedrive. It
            also handles the creation or updating of these records in Pipedrive and logs the results.

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
            api_token = current_instance.api_token if 'api_token' in current_instance else None
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            instance_id = current_instance
            success = True
            created_records, updated_records, no_update_records = 0, 0, 0
            result = None

            for record_id in active_ids:
                record = self.browse(record_id)
                logger_name = 'lead' if record.type == 'lead' else 'deal'
                notification, is_connected = current_instance.sync_record_test_connection('pipedrive', logger_name, current_instance, 'manually')

                # If the connection failed (is_connected is False), return the notification
                if not is_connected:
                    return notification

                if record.sync_to_pipedrive != 'yes' or record.active is not True:
                    if record.sync_to_pipedrive != 'yes':
                        warning_message = f'Sync to Pipedrive is required to be "yes" for record ID {record.id}.'
                    else:
                        warning_message = f'Archived record is not send odoo to pipedrive, record ID {record.id}.'
                    operation = f'Manual {logger_name.capitalize()} Push Odoo To Pipedrive'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                       'pipedrive', record, 'manually', record_id)
                    success = False
                    continue

                if record.type == 'lead':
                    result, pipedrive_id = self.process_crm_odoo_record(instance_id, record, 'lead', 'crm.lead',
                    'leads','pipedriveinstance.leads.lines',
                    'opd.leadmapper', 'leads', 'lead',
                    'odoo_lead_dropdown_mapping', headers,api_token,
                    logger_name, 'manually', check_hash=False)

                    if pipedrive_id:
                        self.process_activities_and_notes(instance_id, record, 'lead', 'crm.lead', api_token, 'manually',
                                                          is_activity=False)
                    else:
                        _logger.info(f'No pipedrive_id found for this record so we can not create activity')

                elif record.type == 'opportunity':
                    result, pipedrive_id = self.process_crm_odoo_record(instance_id, record, 'opportunity', 'crm.lead',
                    'deals', 'pipedriveinstance.deals.lines',
                    'opd.dealmapper', 'deals', 'deal',
                    'odoo_deal_dropdown_mapping', headers,
                    api_token, logger_name, 'manually', check_hash=False)

                    if pipedrive_id:
                        self.process_activities_and_notes(instance_id, record, 'opportunity', 'crm.lead', api_token, 'manually',
                                                          is_activity=False)
                    else:
                        _logger.info(f'No pipedrive_id found for this record so we can not create activity')

                created_records, updated_records, no_update_records, success = self.env['res.partner'].handle_result(
                    result,created_records,updated_records,no_update_records,success)

            return self.env['res.partner'].generate_sync_notification(success, 'pipedrive', logger_name,
                      created_records,updated_records,no_update_records)

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', 'manually', record_id,
                                                             error_type)
            return None

    # ----------------------------- Fetch Company Related Crm Data From Odoo ---------------------------------- #

    def odoo_company_related_crm_data(self, instance_id, odoo_id, pipedrive_record_id,
                                      api_token, model_name,crm_type,pipedrive_model_name,field_model_name,
                                      dropdown_mapping_field, logger_name, operation_type):

        """
           Fetches CRM data related to a company from Odoo and synchronizes it with Pipedrive.

           Args:
               instance_id (Record): The Pipedrive instance to synchronize data with.
               odoo_id (int): The ID of the company in Odoo.
               pipedrive_record_id (int): The ID of the company in Pipedrive.
               api_token (str): The API token for accessing Pipedrive.
               model_name (str): The name of the Odoo model for the CRM records.
               crm_type (str): The type of CRM data to fetch ('lead' or 'opportunity').
               pipedrive_model_name (str): The name of the model in Pipedrive.
               field_model_name (str): The name of the field model in Odoo for mapping fields.
               dropdown_mapping_field (str): The name of the dropdown mapping field.

           Returns:
               None
           """
        crm_record_id, pipedrive_record, crm_endpoint = None, None, None
        try:
            additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'partner_id',
                                 'sync_to_pipedrive', 'tag_ids']
            domain = [
                ('type', '=', crm_type),
                ('partner_id', '=', odoo_id),
                ('sync_to_pipedrive', '=', 'yes'),
                ('active', '=', True)
            ]
            crm_records = self.env['opd.mapper.mixin'].fetch_related_odoo_records(field_model_name, model_name,
                         additional_fields, domain,offset=None, limit=None)
            # Return early if no CRM records found
            if not crm_records:
                return

            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            for crm_record in crm_records:
                crm_record_id = crm_record.get('id') if isinstance(crm_record, dict) else crm_record.id
                crm_pipedrive_id = crm_record.get('pipedrive_id') if isinstance(crm_record, dict) else crm_record.pipedrive_id
                if not crm_record_id:
                    continue
                crm_record_data, dynamic_fields_values_hash, operation_status = self.env[
                    'opd.mapper.mixin'].odoo_to_pipedrive_map_fields(crm_record,
                     instance_id,field_model_name, dropdown_mapping_field, crm_record_id, logger_name, operation_type)
                if operation_status == 'skip':
                    continue

                if crm_record_data:
                    filter_id, odoo_user_id = None, None
                    # Determine filter ID based on CRM type
                    if crm_type == 'lead':
                        # odoo_id_value = self.env['opd.mapper.mixin'].get_odoo_id_field('opd.leadmapper', 'odoo_id')
                        sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.leadmapper', 'odoo_id',
                                                                                        field_name='internal_name')
                        crm_record_data[sync_field] = str(crm_record_id)
                        # filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, crm_record_id, odoo_id_value,
                        #                                     'leads','lead', 'lead', operation_type)

                        if pipedrive_record_id:
                            crm_record_data['organization_id'] = int(pipedrive_record_id)
                        odoo_user_id = self.env['res.users'].set_record_data(crm_record, 'user_id', 'owner_id',
                                                                             crm_record_data)
                        crm_endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'

                    elif crm_type == 'opportunity':
                        sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.dealmapper', 'odoo_id',
                                                                                        field_name='internal_name')

                        # Ensure custom_fields exists
                        if "custom_fields" not in crm_record_data or not isinstance(crm_record_data["custom_fields"], dict):
                            crm_record_data["custom_fields"] = {}

                        # Merge new value instead of replacing the entire dict
                        crm_record_data["custom_fields"][sync_field] = str(crm_record_id)

                        # odoo_id_value = self.env['opd.mapper.mixin'].get_odoo_id_field('opd.dealmapper', 'odoo_id')
                        # filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, crm_record_id, odoo_id_value,
                        #             'deals','deal', 'deal', operation_type)
                        if pipedrive_record_id:
                            crm_record_data['org_id'] = int(pipedrive_record_id)
                        odoo_user_id = self.env['res.users'].set_record_data(crm_record, 'user_id', 'owner_id',
                                                                             crm_record_data)
                        crm_endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'

                    if crm_pipedrive_id:
                        # endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?{crm_pipedrive_id}&api_token={api_token}'
                        payload_rec = {}

                        # Make a GET request to the API endpoint
                        response = self.env['opd.mapper.mixin'].fetch_data(crm_endpoint, headers, payload_rec, method="GET")
                        if response.status_code != 200:
                            error_details = f"{response.status_code} - {response.reason}"
                            description = f"Failed to fetch odoo {logger_name} data."
                            self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, payload_rec,
                            response.text, 'pipedrive', operation_type, crm_record_id,f"HTTP {response.status_code}")

                        response_json = response.json()
                        pipedrive_record = response_json.get('data', [])

                        if pipedrive_record:
                            self.update_pipedrive_record(instance_id, crm_type, pipedrive_model_name, headers,
                            api_token, crm_record_data,dynamic_fields_values_hash,crm_pipedrive_id, crm_record_id,
                            logger_name, odoo_user_id, pipedrive_record, operation_type)

                    else:
                        self.create_pipedrive_record(instance_id, pipedrive_model_name, headers,api_token,crm_record_data,
                              crm_record_id, dynamic_fields_values_hash,logger_name, operation_type)
                else:
                    continue
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related {logger_name} for company ID {pipedrive_record_id} from odoo.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'company', description, 'pipedrive', operation_type, crm_record_id,
                                                             error_type)

    def odoo_contact_related_crm_data(
            self, instance_id, contact_id, pipedrive_record_id,
            api_token, model_name, pipedrive_model_name, field_model_name,
            dropdown_field_mapping_name, crm_type, logger_name, operation_type):

        """
        Optimized v2 CRM sync for contact.
        • No filter_id
        • If pipedrive_id exists → fetch that record → update
        • If not exists or missing → create new
        """

        crm_record_id, odoo_user_id, crm_endpoint = None, None, None
        try:
            additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'partner_id', 'sync_to_pipedrive', 'tag_ids']
            domain = [
                ('type', '=', crm_type),
                ('partner_id', '=', contact_id),
                ('sync_to_pipedrive', '=', 'yes'),
                ('active', '=', True),
            ]

            crm_records = self.env['opd.mapper.mixin'].fetch_related_odoo_records(
                field_model_name, model_name, additional_fields, domain, offset=None, limit=None
            )
            if not crm_records:
                return

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'API Key {api_token}',
            }

            for crm_record in crm_records:

                # --------------------------------------------------
                # Get Odoo ID and existing pipedrive_id
                # --------------------------------------------------
                crm_record_id = crm_record.get('id') if isinstance(crm_record, dict) else crm_record.id
                crm_pipedrive_id = crm_record.get('pipedrive_id') if isinstance(crm_record,
                                                                                dict) else crm_record.pipedrive_id

                if not crm_record_id:
                    continue

                # ---------------- FIELD MAPPING ----------------
                crm_record_data, dynamic_fields_values_hash, operation_status = self.env['opd.mapper.mixin'].odoo_to_pipedrive_map_fields(
                    crm_record, instance_id, field_model_name,dropdown_field_mapping_name, crm_record_id, logger_name, operation_type
                )

                if operation_status == 'skip' or not crm_record_data:
                    continue

                # ---------------- ADD SYNC FIELD + OWNER + contact link ---------------
                if crm_record_data:
                    if crm_type == 'lead':
                        sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper(
                            'opd.leadmapper', 'odoo_id', field_name='internal_name'
                        )
                        crm_record_data[sync_field] = str(crm_record_id)

                        if pipedrive_record_id:
                            crm_record_data['person_id'] = int(pipedrive_record_id)

                        odoo_user_id = self.env['res.users'].set_record_data(
                            crm_record, 'user_id', 'owner_id', crm_record_data
                        )
                        crm_endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'


                    elif crm_type == 'opportunity':
                        sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper(
                            'opd.dealmapper', 'odoo_id', field_name='internal_name'
                        )

                        if "custom_fields" not in crm_record_data:
                            crm_record_data["custom_fields"] = {}

                        crm_record_data["custom_fields"][sync_field] = str(crm_record_id)

                        if pipedrive_record_id:
                            crm_record_data['person_id'] = int(pipedrive_record_id)

                        odoo_user_id = self.env['res.users'].set_record_data(
                            crm_record, 'user_id', 'owner_id', crm_record_data
                        )
                        crm_endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}/{crm_pipedrive_id}?api_token={api_token}'


                    # ---------------------------------------------------
                    # UPDATE FLOW — if pipedrive_id exists
                    # ---------------------------------------------------
                    if crm_pipedrive_id:
                        # First, fetch existing pipedrive crm record
                        payload_rec = {}
                        response = self.env['opd.mapper.mixin'].fetch_data(crm_endpoint, headers, {}, method="GET")
                        if response.status_code != 200:
                            error_details = f"{response.status_code} - {response.reason}"
                            description = f"Failed to fetch odoo {logger_name} data."
                            self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description,
                             payload_rec, response.text, 'pipedrive', operation_type,crm_record_id,
                                                                        f"HTTP {response.status_code}")

                        response_json = response.json()
                        pipedrive_record = response_json.get('data', [])

                        if pipedrive_record:
                            # Record exists → update
                            self.update_pipedrive_record(
                                instance_id, crm_type, pipedrive_model_name, headers, api_token,
                                crm_record_data, dynamic_fields_values_hash, crm_pipedrive_id,
                                crm_record_id, logger_name, odoo_user_id, response.json().get('data'),
                                operation_type
                            )
                            continue  # move to next crm record

                    # ---------------------------------------------------
                    # CREATE FLOW — no pipedrive_id in Odoo
                    # ---------------------------------------------------
                    else:
                        self.create_pipedrive_record(
                            instance_id, pipedrive_model_name, headers, api_token,
                            crm_record_data, crm_record_id, dynamic_fields_values_hash,
                            logger_name, operation_type
                        )
                else:
                    continue

        except Exception as e:
            error_details = str(e)
            description = f"Error occurred while syncing {logger_name} CRM for contact ID {pipedrive_record_id}."
            self.env['opd.mapper.mixin'].exception_log_error(
                error_details, 'contact', description, 'pipedrive', operation_type,
                crm_record_id, 'Exception Error'
            )

    # --------------------- Custom serializer for serializing datetime and date objects to ISO format -------------- #
    def custom_serializer(key, obj):
        """
            Custom serializer for serializing datetime and date objects to ISO format.

            This function checks if the provided object is an instance of `datetime` or `date`.
            If it is, it returns the object in ISO 8601 format. If the object is not serializable,
            it raises a `TypeError`.

            Args:
                key: The key associated with the object to serialize. This is typically used in
                     key-value pairs where the key is a string.
                obj: The object to be serialized. This should be an instance of `datetime` or `date`.

            Returns:
                str: The ISO 8601 formatted string representation of the `datetime` or `date` object.

            Raises:
                TypeError: If the provided object is not serializable (i.e., not an instance of `datetime`
                           or `date`).

            """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    class CrmTag(models.Model):
        _inherit = "crm.tag"

        pipedrive_id = fields.Char("Pipedrive ID")

