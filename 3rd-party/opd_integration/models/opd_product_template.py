# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import requests
from datetime import datetime
import json
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplateInherit(models.Model):
    """
       Description:
           This class inherits the 'product.template' model and adds additional functionality for fetching
           product data from Pipedrive and updating records in Odoo.

       """
    _inherit = 'product.template'
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    pipedrive_id = fields.Char(string='Pipedrive ID')
    sync_to_pipedrive = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Sync To Pipedrive', default='yes')
    odoo_hash = fields.Char(string='Odoo hash')

    @api.model
    def fetch_product_from_pipedrive(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches product data from Pipedrive Create and Update records in Odoo.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Pipedrive product Last Sync Date.
        #        """
        odoo_model_name = 'product.template'  # Define the Odoo model name
        return self.fetch_all_product_from_pipedrive(instance_id, last_sync_date, 'products',
            odoo_model_name,'pipedriveinstance.products.lines',
            'pipedrive_product_dropdown_mapping', 'product', operation_type, check_hash=True)

    @api.model
    def fetch_product_from_odoo(self, instance_id, last_sync_date, operation_type):
        #     """
        #        Description:
        #            Fetches product data from Odoo and Create and Update records in Pipedrive.
        #
        #        Args:
        #            instance_id (str): The Pipedrive instance ID.
        #            last_sync_date (Datetime): The Odoo product Last Sync Date.
        #        """
        odoo_model_name = 'product.template'  # Define the Odoo model name
        return self.fetch_all_product_from_odoo(instance_id, last_sync_date, 'products',
        odoo_model_name,'pipedriveinstance.products.lines',
        'odoo_product_dropdown_mapping', 'product', operation_type)

    def fetch_product_filter_id(self, api_token, value, field_id, type, object, logger_name, last_field_id,
                                last_field_value, operation_type):
        """
        Description:
            Common method to fetch the filter ID from Pipedrive based on certain conditions.

        Args:
            api_token (str): Pipedrive API token.
            field_id (int): ID of the field.
            type (str): Type of the filter (e.g., "org").
            object (str): Type of the object (e.g., "Organization").
            name (str): Name of the filter.
            operator (str): Operator to be used in the filter conditions.
            value (str): Value to be used in the filter conditions.

        Returns:
            str: Filter ID retrieved from Pipedrive.
        """
        try:
            url = f"{self.__API_BASE_URL}filters?api_token={api_token}"
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            payload = json.dumps({
                "name": 'product',
                "type": type,
                "conditions": {
                    "glue": "and",
                    "conditions": [
                        {
                            "glue": "and",
                            "conditions": [
                                {
                                    "object": object,
                                    "field_id": field_id,
                                    "operator": "=",
                                    "value": value,
                                    "extra_value": None
                                },
                                {
                                    "object": object,
                                    "field_id": last_field_id,
                                    "operator": ">",
                                    "value": last_field_value,
                                    "extra_value": None
                                }
                            ]
                        },
                        {
                            "glue": "or",
                            "conditions": []
                        }
                    ]
                },
            })
            response = self.env['opd.mapper.mixin'].fetch_data(url, headers, payload, method="POST")

            if response.status_code in [200, 201]:
                response_json = response.json()
                filter_id = response_json.get('data', {}).get('id')
                if filter_id:
                    self.env['opd.filter'].create({'filter_id': str(filter_id)})
                return filter_id
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive {logger_name} filter ID"
                self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, payload,
                             response.text, 'odoo', operation_type, '', f"HTTP {response.status_code}")
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create {logger_name} filter ID'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '',
                                                             error_type)
            return None

    # --------------------- Fetch ALL Products From Pipedrive (v2 + filter_id + cursor + last_id) ----------------- #
    @api.model
    def fetch_all_product_from_pipedrive(
            self, instance_id, last_sync_date_field, pipedrive_model_name, odoo_model_name,
            field_model_name, dropdown_field_mapping_name, logger_name, operation_type,check_hash=True):
        try:
            # ---------------------- Get Sync Dates ---------------------- #
            last_sync_date, current_utc_time = (
                self.env['opd.mapper.mixin'].last_sync_date_common(last_sync_date_field)
            )

            updated_since = (
                last_sync_date.strftime('%Y-%m-%dT%H:%M:%SZ') if last_sync_date else None
            )

            # ---------------------- Setup ---------------------- #
            api_token = instance_id.api_token
            base_url = instance_id.api_base_url.rstrip("/")
            limit = instance_id.pagination_size or 100

            cursor = None
            record_last_id = instance_id.pipedrive_product_last_id

            # Field mapping check
            is_field_mapping = self.env['opd.mapper.mixin'].has_field_mappings(
                field_model_name, instance_id, logger_name, operation_type
            )
            if not is_field_mapping:
                return

            # ---------------------- MAIN LOOP ---------------------- #
            while True:

                # --- get sync_to_odoo sync_value and field id ---- #
                sync_value, sync_field_id = self.env['opd.mapper.mixin'].get_sync_value(
                    instance_id, field_model_name, dropdown_field_mapping_name,logger_name, operation_type)

                last_field_id = self.env['opd.mapper.mixin'].get_update_time_field('opd.productmapper', 'id')

                # ---------------------- Create v1-style filter ---------------------- #
                if sync_value:
                    product_filter_id = self.fetch_product_filter_id(api_token,sync_value,sync_field_id,"products",
                        "product",logger_name,last_field_id,record_last_id,operation_type)
                else:
                    break

                if not product_filter_id:
                    break

                # ---------------------- Build Endpoint ---------------------- #
                endpoint = (
                    f"{base_url}/{pipedrive_model_name}"
                    f"?filter_id={product_filter_id}"
                    f"&limit={limit}"
                    f"&sort_by=id&sort_direction=asc"
                    f"&api_token={api_token}"
                )

                if updated_since:
                    endpoint += f"&updated_since={updated_since}"

                if cursor:
                    endpoint += f"&cursor={cursor}"

                headers = {'Content-Type': 'application/json',
                           'Authorization': f'API Key {api_token}'}

                response = self.env['opd.mapper.mixin'].fetch_data(
                    endpoint, headers, {}, method="GET"
                )

                if response.status_code != 200:
                    self.env['opd.mapper.mixin'].http_log_error(
                        f"No product found: {response.text}", logger_name,
                        "Error fetching products", {}, response.text,
                        'odoo', operation_type, '', f"HTTP {response.status_code}"
                    )
                    break

                response_json = response.json()
                product_records = response_json.get("data", []) or []
                additional_data = response_json.get("additional_data", {}) or {}

                cursor = additional_data.get("next_cursor")

                # ---------------------- Process Batch ---------------------- #
                if product_records:
                    self.create_or_update_product_record(product_records,instance_id,dropdown_field_mapping_name,
                        odoo_model_name,field_model_name,pipedrive_model_name,api_token,logger_name,
                        operation_type,check_hash=check_hash)

                    # update last_id
                    record_last_id = product_records[-1].get("id")
                    instance_id.write({'pipedrive_product_last_id': record_last_id})
                    instance_id.env.cr.commit()

                # ---------------------- Stop When Cursor Ends ---------------------- #
                if not cursor:
                    break

            # ---------------------- Finalize Sync ---------------------- #
            instance_id.write({
                'pipedrive_product_last_sync_date': current_utc_time,
                'pipedrive_product_last_id': 0
            })

            self.env['opd.mapper.mixin'].scheduler_run_successfully_log(
                logger_name, operation_type, 'odoo'
            )

        except Exception as e:
            self.env['opd.mapper.mixin'].exception_log_error(
                str(e), logger_name,
                f"Error during Product Create/Update from Pipedrive",
                'odoo', operation_type, '', 'Exception Error'
            )

    # ------------ Create or update a record in Odoo based on the provided data ------------- #
    @api.model
    def create_or_update_product_record(self, batch_records, instance_id, dropdown_field_mapping_name,
                                        odoo_model_name,
                                        field_model_name, pipedrive_model_name, api_token, logger_name, operation_type, check_hash=True):
        """
        Create or update a record in Odoo based on the provided data.

        odoo_record: The existing Odoo record, if any.
        record_data: The data to write to the Odoo record.
        dynamic_fields_values_hash: The hash value of the dynamic fields.
        record_id: The ID of the record in Pipedrive.
        odoo_model_name: The name of the Odoo model to update or create.
        field_model_name: The name of the field model.
        pipedrive_model_name: The name of the Pipedrive model.
        api_token: The API token for Pipedrive.
        logger_name: The name of the logger to use for logging operations.

        return: A string indicating the result of the operation ('update', 'create', 'no_update').
        """
        operation_status = None
        for record in batch_records:
            product_id = record.get('id')
            product_code = record.get('code')
            product_category = record.get('category')
            # Iterate over the field mappings

            # Check if product_code or product_category is missing and log a warning
            if not product_category:
                if not product_category:
                    description = f'Product category is a required field in Odoo. Product ID: {product_id}'
                    operation = 'Product send Pipedrive to Odoo'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, description, operation, 'odoo', record, operation_type, product_id)
                    operation_status = 'skip'
                    continue

            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.env[
                'opd.mapper.mixin'].pipedrive_to_odoo_map_fields(record, instance_id,
                field_model_name,dropdown_field_mapping_name, product_id, logger_name, operation_type)
            if operation_status == 'skip':
                continue
            if record_data:
                record_data['pipedrive_id'] = product_id
                record_data['odoo_hash'] = dynamic_fields_values_hash
                # Extract user record using "owner_id"
                user_record = self.env['res.users'].get_user_record(record, "owner_id")
                if user_record:
                    record_data['responsible_id'] = user_record.id

                sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.productmapper',
                   'odoo_id',field_name='internal_name')
                odoo_id = self.env['opd.mapper.mixin']._get_pipedrive_custom_field_value(record, sync_field)

                product, default_code_exists_with_pipedrive_id = self.env['opd.mapper.mixin'].search_product(product_code, odoo_id)

                if default_code_exists_with_pipedrive_id:
                    description = f'The product with the code "{product_code}" already exists in the system. Please use a unique product code.'
                    operation = 'Product send pipedrive to odoo'
                    self.env['opd.mapper.mixin'].log_operation_warning(logger_name, description,
                            operation, 'odoo', product, operation_type, product_id)
                    operation_status = 'skip'
                    continue

                if product:
                    if product.odoo_hash != dynamic_fields_values_hash or not check_hash:
                        product.write(record_data)
                        product.env.cr.commit()
                        self.env['opd.mapper.mixin'].log_operation(logger_name, '', product_id, record_data, 'update',
                                                                   'odoo', operation_type, parent_name=None, parent_id=None)
                        self.env['opd.mapper.mixin'].pipedrive_update_odoo_id(product_id, product,
                        pipedrive_model_name, api_token, logger_name, operation_type)
                        operation_status = 'update'
                    else:
                        operation_status = 'no_update'
                else:
                    new_product = self.env[odoo_model_name].create(record_data)
                    new_product.env.cr.commit()
                    self.env['opd.mapper.mixin'].log_operation(logger_name, '', product_id, record_data, 'create', 'odoo', operation_type, parent_name=None, parent_id=None)
                    self.env['opd.mapper.mixin'].pipedrive_update_odoo_id(product_id, new_product,
                    pipedrive_model_name, api_token,logger_name, operation_type)
                    operation_status = 'create'
        return operation_status

    # -------------------------------- Transfer Product Odoo To Pipedrive -------------------------- #
    def fetch_all_product_from_odoo(self, instance_id, last_sync_date_field, pipedrive_model_name, odoo_model_name,
                                    field_model_name,
                                    dropdown_mapping_field, logger_name, operation_type):
        """
            Fetches all product records from Odoo and syncs them to Pipedrive.

            This function retrieves product records from Odoo that have been updated since the last sync date,
            and synchronizes these records with Pipedrive. It handles pagination to process records in batches,
            and updates the last sync date and the last processed record ID in the instance configuration.

            Parameters:
                instance_id (Record): The instance record containing configuration details for the Pipedrive instance.
                last_sync_date_field (datetime): The field storing the last synchronization date.
                pipedrive_model_name (str): The model name for Pipedrive.
                odoo_model_name (str): The model name for Odoo.
                field_model_name (str): The field model name for mapping fields.
                dropdown_mapping_field (str): The field for dropdown mapping.
                logger_name (str): The logger name for logging operations and errors.

            Returns:
                None

            """
        try:
            limit, offset = self.env['opd.mapper.mixin'].initialize_pagination(instance_id, logger_name, 'pipedrive', operation_type)
            record_last_id = instance_id.odoo_product_last_id
            last_sync_date, current_utc_time = self.env['opd.mapper.mixin'].last_sync_date_common(last_sync_date_field)
            if limit == 0:
                return
            while True:
                additional_fields = ['responsible_id', 'odoo_hash', 'pipedrive_id', 'write_date',
                                     'sync_to_pipedrive']

                product_records = self.env['opd.mapper.mixin'].fetch_odoo_records(field_model_name, instance_id,
                                  odoo_model_name,additional_fields, record_last_id, logger_name, operation_type, is_company=None, crm_type=None,
                                  last_sync_date=last_sync_date,offset=0, limit=limit)

                if product_records:
                    self.sync_product_to_pipedrive(product_records, instance_id, pipedrive_model_name,
                                                   field_model_name, dropdown_mapping_field, operation_type, check_hash=True)

                    record_last_id = product_records[-1].get('id') if isinstance(product_records[-1],
                                                                                 dict) else product_records[-1].id
                    instance_id.write({'odoo_product_last_id': record_last_id})

                    if len(product_records) < limit:
                        break
                else:
                    break

            if last_sync_date:
                instance_id.write({'odoo_product_last_sync_date': current_utc_time})
                instance_id.write({'odoo_product_last_id': 0})
                if product_records:
                    self.env['opd.mapper.mixin'].scheduler_run_successfully_log(logger_name, operation_type, 'pipedrive')
        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, '',
                                                             error_type)

    # ------------------- Synchronizes a product record from Odoo to Pipedrive ---------------- #
    def sync_product_to_pipedrive(self, product_records, instance_id, pipedrive_model_name, field_model_name,
                                  dropdown_mapping_field, operation_type, check_hash=True):
        """
           Synchronizes a product record from Odoo to Pipedrive.

           This method maps the fields of a product record from Odoo to the corresponding fields in Pipedrive.
           It then either creates or updates the product record in Pipedrive based on whether the record
           already exists in Pipedrive. The method logs the operations and handles any errors that occur
           during the synchronization process.

           Args:
               product_record (record): The product record from Odoo that needs to be synchronized.
               instance_id (record): The Pipedrive instance configuration record containing API token and other settings.
               pipedrive_model_name (str): The name of the Pipedrive model for the product (e.g., 'products').
               field_model_name (str): The name of the model containing the field mappings between Odoo and Pipedrive.
               dropdown_mapping_field (str): The name of the field containing dropdown mapping information.

           Returns:
               str: A string indicating the result of the synchronization process:
                    - 'create' if the product record was created in Pipedrive.
                    - 'update' if the product record was updated in Pipedrive.
                    - 'no_update' if no update was necessary (record was already up-to-date).
                    - False if there was an error during the process.
           """
        operation_status = None
        for product_record in product_records:
            odoo_id = product_record.get('id') if isinstance(product_record, dict) else product_record.id
            product_record_data, dynamic_fields_values_hash, operation_status = self.env['opd.mapper.mixin'].odoo_to_pipedrive_map_fields(
                product_record, instance_id, field_model_name, dropdown_mapping_field, odoo_id, 'product', operation_type)

            if operation_status == 'skip':
                continue
            if product_record_data:
                pipedrive_id = product_record.get('pipedrive_id') if isinstance(product_record,
                                                                                dict) else product_record.pipedrive_id
                sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.productmapper', 'odoo_id',
                                                                                field_name='internal_name')
                # Ensure custom_fields exists
                if "custom_fields" not in product_record_data or not isinstance(product_record_data["custom_fields"], dict):
                    product_record_data["custom_fields"] = {}

                # Merge new value instead of replacing the entire dict
                product_record_data["custom_fields"][sync_field] = str(odoo_id)

                odoo_id_value = self.env['opd.mapper.mixin'].get_update_time_field('opd.productmapper', 'id')
                product_code_id = self.env['opd.mapper.mixin'].get_update_time_field('opd.productmapper', 'code')
                product_code_value = product_record.get('default_code') if isinstance(product_record,
                                                                                      dict) else product_record.default_code
                api_token = instance_id.api_token if 'api_token' in instance_id else None
                create_new_record = False  # Flag to indicate if a new record should be created
                if pipedrive_id and product_code_value:
                    filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, pipedrive_id, odoo_id_value,
                                'products','product', 'product', operation_type)
                elif pipedrive_id:
                    filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, pipedrive_id, odoo_id_value,
                                'products','product', 'product', operation_type)
                elif product_code_value:
                    filter_id = self.env['opd.mapper.mixin'].fetch_odoo_id(api_token, product_code_value, product_code_id,
                              'products', 'product', 'product', operation_type)

                    if filter_id:
                        # Fetch the record using the filter_id to check the odoo_id
                        endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?filter_id={filter_id}&api_token={api_token}'
                        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                        pipedrive_record, status_code = self.env['opd.mapper.mixin'].update_or_create_pipedrive_record(
                            {},endpoint,headers,'product', operation_type, method='GET')
                        if pipedrive_record:
                            existing_odoo_id = pipedrive_record[0].get(sync_field) if isinstance(pipedrive_record,
                                                                                                 list) else pipedrive_record.get(
                                sync_field)
                            if existing_odoo_id:
                                description = f'The product with the code "{product_code_value}" already exists in the system. Please use a unique product code.',
                                operation = f'Record Send Odoo To Pipedrive'
                                self.env['opd.mapper.mixin'].log_operation_warning('product', description, operation,
                                'pipedrive', pipedrive_record, operation_type, odoo_id)
                                continue
                else:
                    filter_id = None
                    create_new_record = True  # Set flag to created a new record

                if filter_id:
                    endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?filter_id={filter_id}&api_token={api_token}'
                else:
                    endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, {}, method="GET")
                if response.status_code != 200:
                    self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}", 'product',
                    f"Failed to fetch product filter record",product_record_data,response.text, 'pipedrive',
                    operation_type, odoo_id, f"HTTP {response.status_code}")
                    continue

                pipedrive_record = response.json().get('data', [])
                self.env['res.users'].set_record_data(product_record, 'responsible_id', 'owner_id', product_record_data)
                if pipedrive_record and not create_new_record:
                    odoo_hash = product_record.get('odoo_hash') if isinstance(product_record,
                                                                              dict) else product_record.odoo_hash
                    if odoo_hash != dynamic_fields_values_hash or not check_hash:
                        update_payload = json.dumps(product_record_data)
                        pipedrive_id = pipedrive_record[0]['id'] if isinstance(pipedrive_record, list) else \
                            pipedrive_record['id']
                        odoo_product_record = self.env['product.template'].browse(odoo_id)
                        odoo_product_record.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
                        odoo_product_record.env.cr.commit()
                        update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_id}?api_token={api_token}"
                        response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)
                        self.env['opd.mapper.mixin'].log_operation('product', response.status_code, odoo_id,
                        product_record_data, 'update','pipedrive', operation_type, parent_name=None,parent_id=None)
                        operation_status = 'update'
                        if response.status_code != 200:
                            self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}",
                            'product',f"Failed to update product in pipedrive",product_record_data,
                            response.text, 'pipedrive', operation_type, odoo_id,f"HTTP {response.status_code}")
                            continue
                    else:
                        operation_status = 'no_update'
                else:
                    create_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}"
                    create_payload = json.dumps(product_record_data)
                    response = self.env['opd.mapper.mixin'].fetch_data(create_endpoint, headers, create_payload,
                                                                       method="POST")

                    if response.status_code in [200, 201]:
                        response_json = response.json()
                        pipedrive_id = response_json.get('data', {}).get('id')
                        odoo_product_record = self.env['product.template'].browse(odoo_id)
                        odoo_product_record.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
                        odoo_product_record.env.cr.commit()
                        self.env['opd.mapper.mixin'].log_operation('product', response.status_code, odoo_id,
                         product_record_data, 'create','pipedrive', operation_type, parent_name=None,parent_id=None)
                        operation_status = 'create'
                    else:
                        self.env['opd.mapper.mixin'].http_log_error(f"{response.status_code} - {response.reason}",
                        'product',f"Failed to create product in pipedrive",product_record_data,
                        response.text, 'pipedrive', operation_type, odoo_id,f"HTTP {response.status_code}")
                        continue
            else:
                return None
        return operation_status

    # ---------------- Send Record To Pipedrive From Product Form And Tree View ------------------ #

    def product_send_to_pipedrive(self):
        """
           Synchronizes selected product records from Odoo to Pipedrive.

           This method processes active product records in the current context, synchronizes them with Pipedrive,
           and logs the results of the synchronization process. It handles both the creation and updating of
           product records in Pipedrive and logs any warnings or errors that occur.

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
            notification, is_connected = current_instance.sync_record_test_connection('pipedrive', 'product', current_instance, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
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
            active_ids = self._context.get('active_ids', [self.id]) if self._context.get('active_ids') else [self.id]
            for record_id in active_ids:
                record = self.browse(record_id)
                if record.sync_to_pipedrive != 'yes' or record.active is not True:
                    if record.sync_to_pipedrive != 'yes':
                        warning_message = f'Sync to Pipedrive is required to be "Yes" for record ID {record.id}.'
                    else:
                        warning_message = f'Archived record is not send odoo to pipedrive, record ID {record.id}.'
                    operation = f'Manual Product Push Odoo To Pipedrive'
                    self.env['opd.mapper.mixin'].log_operation_warning('product', warning_message, operation,
                                                                       'pipedrive', record, 'manually', record_id)
                    success = False
                    continue
                result = self.sync_product_to_pipedrive(record, instance_id, 'products',
                                                        'pipedriveinstance.products.lines',
                                                        'odoo_product_dropdown_mapping', 'manually', check_hash=False)
                created_records, updated_records, no_update_records, success = self.env['res.partner'].handle_result(
                    result,created_records,updated_records, no_update_records, success)

            return self.env['res.partner'].generate_sync_notification(success, 'pipedrive', 'product', created_records,
                            updated_records,no_update_records)
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while product create/update in pipedrive.'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'product', description, 'pipedrive', 'manually', record_id,
                                                             error_type)
            return None
