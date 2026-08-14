from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ManualPdToOdoo(models.TransientModel):
    """
        The ManualPdToOdoo class is a transient model designed to facilitate the manual transfer of records
        from Pipedrive to Odoo. This class allows users to specify which module and record from Pipedrive they want to send to Odoo
    """
    _name = "opd.pipedrivetoodoowizard"
    _description = "Manual Record Send Pipedrive To Odoo"
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_module_name = fields.Selection(
        [('company', 'Company'), ('contact', 'Contact'), ('deal', 'Opportunity'), ('lead', 'Lead'),
         ('product', 'Product'), ('user', 'User')],
        string='Pipedrive Module Name', required=True)
    pipedrive_record_id = fields.Text(string='Pipedrive Record IDs', required=True)

    # -------------------------- Send a record from Pipedrive to Odoo ----------------------- #

    def action_send_record_pipedrive_to_odoo(self):
        """
            Dispatches the action to send a record from Pipedrive to Odoo based on the Pipedrive module name.

            This function checks the Pipedrive module name and record ID to determine which specific function to
            call to handle the synchronization of the record from Pipedrive to Odoo. It handles different types
            of records such as organization, person, lead, deal, product, and user.

            return: None
        """
        total_record_ids, record_ids, message = None, None, None

        # Call test_connection to check if the connection is successful
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        notification, is_connected = current_instance.sync_record_test_connection('odoo', self.pipedrive_module_name, current_instance, 'manually')

        # If the connection failed (is_connected is False), return the notification
        if not is_connected:
            return notification
        if self.pipedrive_module_name == 'company' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_partner_record_pipedrive_to_odoo(
                'pipedrive_company_dropdown_mapping',
                'pipedriveinstance.companies.lines', 'opd.companymapper',
                'company', 'organizations', 'org', 'organization', True,
                self.pipedrive_record_id)

        elif self.pipedrive_module_name == 'contact' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_partner_record_pipedrive_to_odoo(
                'pipedrive_contacts_dropdown_mapping',
                'pipedriveinstance.contacts.lines', 'opd.contactmapper',
                'contact', 'persons', 'people', 'person', False, self.pipedrive_record_id)
        elif self.pipedrive_module_name == 'lead' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_crm_record_pipedrive_to_odoo(
                'pipedrive_lead_dropdown_mapping',
                'pipedriveinstance.leads.lines', 'opd.leadmapper',
                'lead', 'leads', 'leads', 'lead', 'lead', 'is_lead_calls',
                'is_lead_tasks','is_lead_emails','is_lead_meetings',
                'is_lead_notes', self.pipedrive_record_id)
        elif self.pipedrive_module_name == 'deal' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_crm_record_pipedrive_to_odoo(
                'pipedrive_deal_dropdown_mapping',
                'pipedriveinstance.deals.lines', 'opd.dealmapper',
                'deal', 'deals', 'deals', 'deal', 'opportunity', 'is_deal_calls',
                'is_deal_tasks','is_deal_emails','is_deal_meetings',
                'is_deal_notes', self.pipedrive_record_id)
        elif self.pipedrive_module_name == 'product' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_product_record_pipedrive_to_odoo(
                'pipedrive_product_dropdown_mapping',
                'pipedriveinstance.products.lines','opd.productmapper',
                'product', 'products', 'products', 'product',
                self.pipedrive_record_id)
        elif self.pipedrive_module_name == 'user' and self.pipedrive_record_id:
            message, total_record_ids, record_ids = self.send_user_record_pipedrive_to_odoo('user', 'users',
                                                                                            self.pipedrive_record_id)

        if message:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': f"{message}. Total {total_record_ids} Ids: {record_ids}",
                },
            }
        else:
            message = "Please Check The Pipedrive Logger"
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': message},
            }

    # -------------------------- Send a partner record from Pipedrive to Odoo -------------------------- #
    def send_partner_record_pipedrive_to_odoo(self, dropdown_field_mapping_name, field_model_name, field_mapper_model,
                                              logger_name, pipedrive_model_name, type, object, is_company, id_values):
        """
            Send a partner record from Pipedrive to Odoo.

            This function fetches a partner record (organization or person) from Pipedrive, maps the fields to Odoo,
            and either creates a new record or updates an existing one in Odoo.

            dropdown_field_mapping_name: The name of the dropdown field mapping.
            field_model_name: The name of the field model.
            field_mapper_model: The model used for field mapping.
            logger_name: The name of the logger to use for logging operations.
            pipedrive_model_name: The name of the Pipedrive model to fetch data from.
            type: The type of the object being fetched.
            object: The object being fetched.
            is_company: A boolean indicating if the record is a company (True) or a person (False).

            return: None
        """
        partner_id = None
        try:
            total_record_ids = 0
            partner_record_ids = []
            message = None
            pipedrive_record_ids_list = id_values.split(',')
            if not pipedrive_record_ids_list:
                return None, None, None
            for partner_id in pipedrive_record_ids_list:
                if not partner_id:
                    continue
                partner_id = partner_id.strip()
                response, instance_id, sync_value, api_token = \
                    self.env['opd.pipedrivetoodoowizard'].fetch_pipedrive_data(field_model_name,
                    dropdown_field_mapping_name,field_mapper_model,logger_name, pipedrive_model_name, type,
                    object, partner_id)

                if not sync_value:
                    continue
                if response:
                    if response.status_code == 200:
                        response_json = response.json()
                        record = response_json.get('data', [])
                        if record:
                            total_record_ids += 1
                            partner_record_ids.append(partner_id)
                            # Get sync field internal key from mapper (e.g., 'd19ba21c71dd881c63289753bea5e273534251f7')
                            sync_field = self.env['opd.mapper.mixin'].get_sync_to_odoo(field_mapper_model)

                            # Normalize record (if list)
                            record_data = record[0] if isinstance(record, list) else record

                            # New response structure in v2
                            custom_fields = record_data.get('custom_fields', {})
                            # Try to get sync_to_odoo from custom_fields or fallback to root-level
                            sync_to_odoo = (custom_fields.get(sync_field) or record_data.get(sync_field)
                                or False)

                            if sync_to_odoo:
                                sync_to_odoo = int(sync_to_odoo)
                            record_id = record[0]['id'] if isinstance(record, list) else record.get('id')
                            record = record if isinstance(record, list) else [record]
                            if sync_to_odoo == sync_value:
                                if not is_company:
                                    result = self.env['opd.mapper.mixin'].process_partner_contact(
                                        record, instance_id,'res.partner','is_contact_calls','is_contact_tasks',
                                        'is_contact_emails','is_contact_meetings','is_contact_notes',api_token,
                                        logger_name,field_model_name,pipedrive_model_name,dropdown_field_mapping_name,
                                        'manually',check_hash=False)
                                    if result in ['create', 'update', 'no_update']:
                                        message = f"Records Successfully Created/Updated"

                                elif is_company:
                                    self.env['opd.mapper.mixin'].process_partner_company(
                                    record,instance_id,'res.partner','is_company_calls',
                                    'is_company_tasks','is_company_emails','is_company_meetings',
                                    'is_company_notes',api_token, logger_name,field_model_name,pipedrive_model_name,
                                    dropdown_field_mapping_name, 'manually', check_hash=False)
                                    message = f"Records Successfully Created/Updated"

                            else:
                                total_record_ids -= 1
                                warning_message = f'Please set value of sync_to_doo Yes for {logger_name.capitalize()} ID : {record_id}'
                                operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                                self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                                   'odoo', record, 'manually', record_id)

                        else:
                            warning_message = f'No record found for this {logger_name.capitalize()} ID : {partner_id}'
                            operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                            self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                               'odoo', record, 'manually', partner_id)

                    else:
                        error_details = f"{response.status_code} - {response.reason}"
                        description = f"Failed to fetch Pipedrive {pipedrive_model_name} data."
                        self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, {},
                                                                    response.text, 'odoo', 'manually', partner_id,
                                                                    f"HTTP {response.status_code}")
                else:
                    continue
            return message, total_record_ids, partner_record_ids

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while sending {logger_name} record pipedrive to odoo'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'odoo', 'manually',
                                                             partner_id, error_type)
            return None, None, None

    # -------------------------- Send a CRM record from Pipedrive to Odoo. --------------------- #
    def send_crm_record_pipedrive_to_odoo(self, dropdown_field_mapping_name, field_model_name, field_mapper_model,
                                          logger_name, pipedrive_model_name, type, object, crm_type, calls_field,
                                          tasks_field, emails_field, meetings_field,notes_field, id_values):
        """
            Send a CRM record from Pipedrive to Odoo.

            This function fetches a CRM record (lead or deal) from Pipedrive, maps the fields to Odoo,
            and either creates a new record or updates an existing one in Odoo.

            dropdown_field_mapping_name: The name of the dropdown field mapping.
            field_model_name: The name of the field model.
            field_mapper_model: The model used for field mapping.
            logger_name: The name of the logger to use for logging operations.
            pipedrive_model_name: The name of the Pipedrive model to fetch data from.
            type: The type of the object being fetched.
            object: The object being fetched.
            crm_type: The type of the CRM record (e.g., lead, deal).
            calls_field: The field for calls activities.
            tasks_field: The field for tasks activities.
            emails_field: The field for emails activities.
            meetings_field: The field for meetings activities.
            notes_field: The field for notes activities.

            return: None
        """
        crm_id = None
        try:
            total_record_ids = 0
            crm_record_ids = []
            message = None
            pipedrive_record_ids_list = id_values.split(',')
            if not pipedrive_record_ids_list:
                return None, None, None
            for crm_id in pipedrive_record_ids_list:
                if not crm_id:
                    continue
                crm_id = crm_id.strip()
                response, instance_id, sync_value, api_token = \
                    self.env['opd.pipedrivetoodoowizard'].fetch_pipedrive_data(
                    field_model_name, dropdown_field_mapping_name,field_mapper_model,
                    logger_name, pipedrive_model_name, type,object, crm_id)
                if not sync_value:
                    continue
                if response:
                    if response.status_code == 200:
                        response_json = response.json()
                        record = response_json.get('data', [])

                        if record:
                            total_record_ids += 1
                            crm_record_ids.append(crm_id)
                            # Iterate over the field mappings
                            # Normalize record (if list)
                            record_data = record[0] if isinstance(record, list) else record
                            sync_field = self.env['opd.mapper.mixin'].get_sync_to_odoo(field_mapper_model)
                            if logger_name == 'deal':
                                sync_to_odoo = self.env['opd.mapper.mixin']._get_pipedrive_custom_field_value(
                                    record_data, sync_field
                                )
                            else:
                                sync_to_odoo = self.env['opd.mapper.mixin']._get_pipedrive_custom_field_value(
                                    record_data, sync_field
                                )

                            if sync_to_odoo:
                                sync_to_odoo = int(sync_to_odoo)

                            record_id = record[0]['id'] if isinstance(record, list) else record.get('id')
                            if sync_to_odoo == sync_value:
                                record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.env[
                                    'opd.mapper.mixin'].pipedrive_to_odoo_map_fields(
                                    record,instance_id,field_model_name,
                                    dropdown_field_mapping_name, record_id, logger_name, 'manually')

                                if operation_status == 'skip':
                                    continue
                                if record_data:
                                    record_data['pipedrive_id'] = record_id
                                    record_data['type'] = crm_type
                                    record_data['odoo_hash'] = dynamic_fields_values_hash
                                    # Extract user record using "owner_id"
                                    user_record = self.env['opd.mapper.mixin'].get_user_record(record_data, crm_type)
                                    if user_record:
                                        record_data['user_id'] = user_record.id

                                    odoo_record = self.env['crm.lead'].search(
                                        [('pipedrive_id', '=', record_id), ('type', '=', crm_type),
                                         ('sync_to_pipedrive', '=', 'yes'), ('active', '=', True)], limit=1)
                                    # Skip activities and notes handling for crm.lead
                                    # Proceed to create or update the record
                                    if odoo_record:
                                        self.env['opd.mapper.mixin'].update_crm_odoo_record(
                                        api_token, odoo_record,record_data,record_id,logger_name,field_model_name,
                                        dropdown_field_mapping_name,pipedrive_model_name, crm_type,instance_id,
                                        calls_field,tasks_field,emails_field,meetings_field,notes_field,
                                       'crm.lead',record,'manually', check_hash=False)

                                        message = f"Records Successfully Created/Updated"

                                    else:
                                        self.env['opd.mapper.mixin'].create_crm_odoo_record(
                                        api_token, 'crm.lead', record_data, record_id,logger_name,pipedrive_model_name,
                                        crm_type,instance_id, calls_field,tasks_field,emails_field,meetings_field,
                                            notes_field, record, 'manually',check_hash=False)
                                        message = f"Records Successfully Created/Updated"
                            else:
                                total_record_ids -= 1
                                warning_message = f'Please set value of sync_to_doo Yes for {logger_name.capitalize()} ID : {record_id}'
                                operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                                self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                                   'odoo', record, 'manually', record_id)

                        else:
                            warning_message = f'No record found for this {logger_name.capitalize()} ID : {crm_id}'
                            operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                            self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                               'odoo', record, 'manually', crm_id)

                    else:
                        error_details = f"{response.status_code} - {response.reason}"
                        description = f"Failed to fetch Pipedrive {pipedrive_model_name} data."
                        self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, {},
                                                                    response.text, 'odoo', 'manually', crm_id,
                                                                    f"HTTP {response.status_code}")
                else:
                    continue
            return message, total_record_ids, crm_record_ids

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while sending {logger_name} record pipedrive to odoo'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'odoo', 'manually', crm_id,
                                                             error_type)
            return None, None, None

    # ---------------------------- Send a product record from Pipedrive to Odoo --------------------------------- #
    def send_product_record_pipedrive_to_odoo(self, dropdown_field_mapping_name, field_model_name, field_mapper_model,
                                              logger_name, pipedrive_model_name, type, object, id_values):
        """
            Send a product record from Pipedrive to Odoo.

            This function fetches a product record from Pipedrive, maps the fields to Odoo,
            and either creates a new record or updates an existing one in Odoo.

            dropdown_field_mapping_name: The name of the dropdown field mapping.
            field_model_name: The name of the field model.
            field_mapper_model: The model used for field mapping.
            logger_name: The name of the logger to use for logging operations.
            pipedrive_model_name: The name of the Pipedrive model to fetch data from.
            type: The type of the object being fetched.
            object: The object being fetched.

            return: None
        """
        product_id = None
        try:
            total_record_ids = 0
            product_record_ids = []
            message = None
            pipedrive_record_ids_list = id_values.split(',')
            if not pipedrive_record_ids_list:
                return None, None, None
            for product_id in pipedrive_record_ids_list:
                if not product_id:
                    continue
                product_id = product_id.strip()
                response, instance_id, sync_value, api_token = \
                    self.env['opd.pipedrivetoodoowizard'].fetch_pipedrive_data(
                    field_model_name,dropdown_field_mapping_name,field_mapper_model,logger_name, pipedrive_model_name,
                        type,object, product_id)
                if not sync_value:
                    continue
                if response:
                    if response.status_code == 200:
                        response_json = response.json()
                        record = response_json.get('data', [])
                        if record:
                            total_record_ids += 1
                            product_record_ids.append(product_id)
                            sync_field = self.env['opd.mapper.mixin'].get_sync_to_odoo('opd.productmapper')
                            record_data = record[0] if isinstance(record, list) else record
                            product_id = record_data.get('id')
                            sync_to_odoo = self.env['opd.mapper.mixin']._get_pipedrive_custom_field_value(
                                record_data, sync_field
                            )
                            if sync_to_odoo:
                                sync_to_odoo = int(sync_to_odoo)
                            sync_value = int(sync_value)
                            if sync_to_odoo == sync_value:
                                record = record if isinstance(record, list) else [record]
                                result = self.env['product.template'].create_or_update_product_record(
                                    record, instance_id, dropdown_field_mapping_name,'product.template',
                                    field_model_name,pipedrive_model_name,api_token,logger_name, 'manually',
                                    check_hash=False)
                                if result in ['create', 'update', 'no_update']:
                                    message = f"Records Successfully Created/Updated"

                            else:
                                total_record_ids -= 1
                                warning_message = f'Please set value of sync_to_doo Yes for {logger_name.capitalize()} ID : {product_id}'
                                operation = f'Manual Push {logger_name} Pipedrive To Odoo'
                                self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                                   'odoo', record, 'manually', product_id)
                        else:
                            warning_message = f'No record found for this {logger_name.capitalize()} ID : {product_id}'
                            operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                            self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                               'odoo', record, 'manually', product_id)

                    else:
                        error_details = f"{response.status_code} - {response.reason}"
                        description = f"Failed to fetch Pipedrive {pipedrive_model_name} data."
                        self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, {},
                        response.text, 'odoo', 'manually', product_id,f"HTTP {response.status_code}")
                else:
                    continue
            return message, total_record_ids, product_record_ids

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while sending {logger_name} record pipedrive to odoo'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'odoo', 'manually', product_id,
                                                             error_type)
            return None, None, None

    # ------------------------- Send a user record from Pipedrive to Odoo ---------------- #
    def send_user_record_pipedrive_to_odoo(self, logger_name, pipedrive_model_name, id_values):
        """
            Send a user record from Pipedrive to Odoo.

            This function fetches a user record from Pipedrive based on the Pipedrive user ID,
            maps the data to the Odoo user model, and either creates a new user or updates an existing
            one in Odoo.

            logger_name: The name of the logger to use for logging operations.
            pipedrive_model_name: The name of the Pipedrive model to fetch the user record from.

            return: None
        """
        user_id = None
        try:
            total_record_ids = 0
            user_record_ids = []
            message = None
            pipedrive_record_ids_list = id_values.split(',')
            if not pipedrive_record_ids_list:
                return None, None, None
            for user_id in pipedrive_record_ids_list:
                if not user_id:
                    continue
                user_id = user_id.strip()
                current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)

                if not current_instance:
                    warning_message = 'No current Pipedrive instance found.'
                    operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation, 'odoo',
                                                                       '', 'manually', user_id)
                    continue
                api_token = current_instance.api_token if 'api_token' in current_instance else None

                endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}/{user_id}?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                payload_rec = {}

                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")

                if response.status_code == 200:
                    response_json = response.json()
                    record = response_json.get('data', [])
                    active_flag = record.get('active_flag')

                    if record and active_flag:
                        total_record_ids += 1
                        user_record_ids.append(user_id)
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
                            [('login', '=', user_email), ('pipedrive_id', '=', user_id), ('share', '=', False),
                             ('active', '=', True)])

                        if user_record:
                            user_record.write(record_data)
                            user_record.env.cr.commit()
                            self.env['opd.mapper.mixin'].log_operation('user', '', user_id, record_data,
                                                                       'update', 'odoo', 'manually', parent_name=None,
                                                                       parent_id=None)
                            message = f"Records Successfully Created/Updated"
                        else:
                            user_record = self.env['res.users'].create(record_data)
                            user_record.env.cr.commit()
                            self.env['opd.mapper.mixin'].log_operation('user', '', user_id, record_data,
                                                                       'create', 'odoo', 'manually', parent_name=None,
                                                                       parent_id=None)
                            message = f"Records Successfully Created/Updated"
                    else:
                        warning_message = f'No record found for this {logger_name.capitalize()} ID : {user_id}'
                        operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                        self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                                                           'odoo', record, 'manually', user_id)

                else:
                    warning_message = f'No record found for this {logger_name.capitalize()} ID : {user_id}'
                    operation = f'Manual {logger_name} Push Pipedrive To Odoo'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation,
                                 'odoo', response.text, 'manually', user_id)
            return message, total_record_ids, user_record_ids

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while sending {logger_name} record pipedrive to odoo'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'odoo', 'manually', user_id,
                                                             error_type)
            return None, None, None

    # ---------------------- Fetch data from Pipedrive and prepare it for synchronization with Odoo -------------- #
    def fetch_pipedrive_data(self, field_model_name, dropdown_field_mapping_name, field_mapper_model, logger_name,
                             pipedrive_model_name, type, object, id_value):

        """
            Fetch data from Pipedrive and prepare it for synchronization with Odoo.

            This function retrieves the current Pipedrive instance, constructs the API endpoint,
            and fetches data from Pipedrive. It also retrieves the necessary synchronization values.

            field_model_name: The name of the field model.
            dropdown_field_mapping_name: The name of the dropdown field mapping.
            field_mapper_model: The model used for field mapping.
            logger_name: The name of the logger to use for logging operations.
            pipedrive_model_name: The name of the Pipedrive model to fetch data from.
            type: The type of the object being fetched.
            object: The object being fetched.

            return: A tuple containing the response, instance ID, success status, created records count,
                     updated records count, no update records count, sync value, API token, ID value, and result.
        """
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)

        if not current_instance:
            warning_message = 'No current Pipedrive instance found.'
            operation = f'Manual {logger_name} Push Pipedrive To Odoo'
            self.env['opd.mapper.mixin'].log_operation_warning(logger_name, warning_message, operation, 'odoo', {}, 'manually', '')
            return None, None, None, None

        instance_id = current_instance
        sync_value, sync_field_id = self.env['opd.mapper.mixin'].get_sync_value(instance_id, field_model_name,
                                    dropdown_field_mapping_name, logger_name, 'manually')
        if sync_value:
            sync_value = int(sync_value)
        else:
            return None, None, None, None
        api_token = instance_id.api_token if 'api_token' in instance_id else None
        if logger_name != 'lead':
            endpoint = f'{current_instance.api_base_url}/{pipedrive_model_name}/{id_value}?api_token={api_token}'
        else:
            endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}/{id_value}?api_token={api_token}'
        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
        payload_rec = {}

        response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")
        return response, instance_id, sync_value, api_token


# ---------------------- Odoo Res Partner Wizard That Manually Send Record Pipedrive to Odoo ------------- #
class PartnerManualPdToOdoo(models.TransientModel):
    """
        The ManualPdToOdoo class is a transient model designed to facilitate the manual transfer of records
        from Pipedrive to Odoo. This class allows users to specify Contacts Module and record from Pipedrive they want to send to Odoo
    """
    _name = "opd.pto.partner.wizard"
    _description = "Manual Partner Record Send Pipedrive To Odoo"

    pipedrive_partner_module = fields.Selection(
        [('company', 'Company'), ('contact', 'Contact')],
        string='Pipedrive Module Name', required=True)
    pipedrive_record_id = fields.Text(string='Pipedrive Record IDs', required=True)

    def action_send_partner_record_pipedrive_to_odoo(self):
        # Call test_connection to check if the connection is successful
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        notification, is_connected = current_instance.sync_record_test_connection('odoo', self.pipedrive_partner_module, current_instance, 'manually')

        # If the connection failed (is_connected is False), return the notification
        if not is_connected:
            return notification

        total_record_ids, partner_record_ids, message = None, None, None

        if self.pipedrive_partner_module == 'company' and self.pipedrive_record_id:
            message, total_record_ids, partner_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_partner_record_pipedrive_to_odoo(
                'pipedrive_company_dropdown_mapping',
                'pipedriveinstance.companies.lines', 'opd.companymapper',
                'company', 'organizations', 'org', 'organization', True, self.pipedrive_record_id)

        elif self.pipedrive_partner_module == 'contact' and self.pipedrive_record_id:
            message, total_record_ids, partner_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_partner_record_pipedrive_to_odoo(
                'pipedrive_contacts_dropdown_mapping',
                'pipedriveinstance.contacts.lines', 'opd.contactmapper',
                'contact', 'persons', 'people', 'person', False, self.pipedrive_record_id)
        if message:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': f"{message}. Total {total_record_ids} Ids: {partner_record_ids}",
                },
            }
        else:
            message = "Please Check The Pipedrive Logger"
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': message},
            }


# ---------------------- Odoo CRM Wizard That Manually Send Record Pipedrive to Odoo ------------- #


class CrmManualPdToOdoo(models.TransientModel):
    """
        The ManualPdToOdoo class is a transient model designed to facilitate the manual transfer of records
        from Pipedrive to Odoo. This class allows users to specify CRM Module record from Pipedrive they want to send to Odoo
    """
    _name = "opd.pto.crm.wizard"
    _description = "Manual CRM Record Send Pipedrive To Odoo"

    pipedrive_crm_module = fields.Selection(
        [('deal', 'Opportunity'), ('lead', 'Lead')],
        string='Pipedrive Module Name', required=True)
    pipedrive_record_id = fields.Text(string='Pipedrive Record IDs', required=True)

    def action_send_crm_record_pipedrive_to_odoo(self):
        # Call test_connection to check if the connection is successful
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        notification, is_connected = current_instance.sync_record_test_connection('odoo', self.pipedrive_crm_module, current_instance, 'manually')

        # If the connection failed (is_connected is False), return the notification
        if not is_connected:
            return notification
        total_record_ids, crm_record_ids, message = None, None, None

        if self.pipedrive_crm_module == 'lead' and self.pipedrive_record_id:
            message, total_record_ids, crm_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_crm_record_pipedrive_to_odoo(
                'pipedrive_lead_dropdown_mapping','pipedriveinstance.leads.lines',
                'opd.leadmapper','lead', 'leads', 'leads', 'lead',
                'lead', 'is_lead_calls','is_lead_tasks','is_lead_emails',
                'is_lead_meetings','is_lead_notes',self.pipedrive_record_id)

        elif self.pipedrive_crm_module == 'deal' and self.pipedrive_record_id:
            message, total_record_ids, crm_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_crm_record_pipedrive_to_odoo(
                'pipedrive_deal_dropdown_mapping','pipedriveinstance.deals.lines',
                'opd.dealmapper','deal', 'deals', 'deals', 'deal',
                'opportunity', 'is_deal_calls','is_deal_tasks','is_deal_emails',
                'is_deal_meetings', 'is_deal_notes', self.pipedrive_record_id)

        if message:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': f"{message}. Total {total_record_ids} Ids: {crm_record_ids}",
                },
            }
        else:
            message = "Please Check The Pipedrive Logger"
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': message},
            }


# ---------------------- Odoo Product Wizard That Manually Send Record Pipedrive to Odoo ------------- #

class ProductManualPdToOdoo(models.TransientModel):
    """
        The ManualPdToOdoo class is a transient model designed to facilitate the manual transfer of records
        from Pipedrive to Odoo. This class allows users to product module and record from Pipedrive they want to send to Odoo
    """
    _name = "opd.pto.product.wizard"
    _description = "Manual Product Record Send Pipedrive To Odoo"

    pipedrive_product_module = fields.Selection(
        [('product', 'Product')],
        string='Pipedrive Module Name', required=True)
    pipedrive_record_id = fields.Text(string='Pipedrive Record IDs', required=True)

    def action_send_product_record_pipedrive_to_odoo(self):
        # Call test_connection to check if the connection is successful
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        notification, is_connected = current_instance.sync_record_test_connection('odoo', self.pipedrive_product_module, current_instance, 'manually')

        # If the connection failed (is_connected is False), return the notification
        if not is_connected:
            return notification
        total_record_ids, product_record_ids, message = None, None, None

        if self.pipedrive_product_module == 'product' and self.pipedrive_record_id:
            message, total_record_ids, product_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_product_record_pipedrive_to_odoo(
                'pipedrive_product_dropdown_mapping','pipedriveinstance.products.lines',
                'opd.productmapper','product', 'products', 'products', 'product', self.pipedrive_record_id)
        if message:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': f"{message}. Total {total_record_ids} Ids: {product_record_ids}",
                },
            }
        else:
            message = "Please Check The Pipedrive Logger"
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': message},
            }


# ---------------------- Odoo Res User Wizard That Manually Send Record Pipedrive to Odoo ------------- #

class UserManualPdToOdoo(models.TransientModel):
    """
        The ManualPdToOdoo class is a transient model designed to facilitate the manual transfer of records
        from Pipedrive to Odoo. This class allows users to specify which module and record from Pipedrive they want to send to Odoo
    """
    _name = "opd.pto.user.wizard"
    _description = "Manual User Record Send Pipedrive To Odoo"

    pipedrive_user_module = fields.Selection(
        [('user', 'User')],
        string='Pipedrive Module Name', required=True)
    pipedrive_record_id = fields.Text(string='Pipedrive Record IDs', required=True)

    def action_send_user_record_pipedrive_to_odoo(self):
        # Call test_connection to check if the connection is successful
        current_instance = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        notification, is_connected = current_instance.sync_record_test_connection('odoo', self.pipedrive_user_module, current_instance, 'manually')

        # If the connection failed (is_connected is False), return the notification
        if not is_connected:
            return notification
        total_record_ids, user_record_ids, message = None, None, None

        if self.pipedrive_user_module == 'user' and self.pipedrive_record_id:
            message, total_record_ids, user_record_ids = self.env[
                'opd.pipedrivetoodoowizard'].send_user_record_pipedrive_to_odoo('user', 'users',
                                                                                self.pipedrive_record_id)
        if message:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'type': 'success', 'sticky': False,
                    'message': f"{message}. Total {total_record_ids} Ids: {user_record_ids}",
                },
            }
        else:
            message = "Please Check The Pipedrive Logger"
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'type': 'warning', 'sticky': False, 'message': message},
            }
