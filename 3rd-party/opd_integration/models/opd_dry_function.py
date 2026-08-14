import ast
import base64

from odoo import api, fields, models, _
import requests
import json
from datetime import datetime
import pytz
from odoo.exceptions import UserError
import logging
import hashlib
from bs4 import BeautifulSoup
import re

_logger = logging.getLogger(__name__)

REQUIRED_PIPEDRIVE_SYNC_FIELDS = [
    {
        'name': 'sync_to_odoo',
        'field_type': 'enum',
        'options': [
            {'label': 'Yes'},
            {'label': 'No'},
        ],
    },
    {
        'name': 'odoo_id',
        'field_type': 'text',
    },
]

PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG = {
    'company': {
        'endpoint': 'organizationFields',
        'display_name': 'Company',
        'mapper_model': 'opd.companymapper',
        'fetch_fields_method': 'fetch_and_store_company_fields',
        'logger_name': 'company',
    },
    'contact': {
        'endpoint': 'personFields',
        'display_name': 'Contact',
        'mapper_model': 'opd.contactmapper',
        'fetch_fields_method': 'fetch_and_store_contact_fields',
        'logger_name': 'contact',
    },
    'lead': {
        'endpoint': 'leadFields',
        'display_name': 'Lead',
        'mapper_model': 'opd.leadmapper',
        'fetch_fields_method': 'fetch_and_store_lead_fields',
        'logger_name': 'lead',
        'supports_field_creation': False,
    },
    'deal': {
        'endpoint': 'dealFields',
        'display_name': 'Opportunity',
        'mapper_model': 'opd.dealmapper',
        'fetch_fields_method': 'fetch_and_store_deal_fields',
        'logger_name': 'deal',
    },
    'product': {
        'endpoint': 'productFields',
        'display_name': 'Product',
        'mapper_model': 'opd.productmapper',
        'fetch_fields_method': 'fetch_and_store_product_fields',
        'logger_name': 'product',
    },
}


class MapperMixin(models.AbstractModel):
    """
        Abstract model for mixing common functionality related to all modules.
    """
    _name = "opd.mapper.mixin"
    _description = "Mapper Mixin"
    __API_BASE_URL = 'https://api.pipedrive.com/v1/'

    # ------------------------- Fetch Odoo And Pipedrive Module Fields -------------------------- #
    @api.model
    def fetch_and_store_fields(self, table_name, field_name, mapper_model, logger_name, mapper_id_field, mapper_lines_field):
        """
                Description:
                            Fetches fields from a database table and an external API endpoint,
                            then stores them in the specified Odoo model.

                Create Date: 3 April 2024.
                Return:
                    count(int): The number of fields stored in the Odoo model.
                """
        try:
            # Fetch the instance name of the pipedrive
            pipedrive_instances = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            if not pipedrive_instances:
                description = _('No connected Pipedrive instance found. Please connect an instance first.')
                self.log_operation_warning(logger_name, description, _('Import Fields'), 'odoo', {}, 'manually', '')
                return -1
            if logger_name in PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG:
                self.ensure_pipedrive_required_custom_fields(
                    pipedrive_instances, logger_name, operation_type='manually', refresh_fields=False
                )
            instance_name = pipedrive_instances.name
            system_odoo = 'Odoo'
            count = 0

            # Fetch odoo fields from the database table
            cr = self.env.cr
            cr.execute(
                f"""
                    SELECT isc.column_name, isc.data_type, imf.field_description
                    FROM information_schema.columns isc
                    JOIN ir_model_fields imf
                    ON isc.column_name = imf.name
                    WHERE isc.table_name = '{table_name}'
                    AND imf.model = '{table_name.replace('_', '.')}'""")
            results = cr.fetchall()

            # Store or update fetched odoo fields in the mapper model
            for column_name, data_type, field_description in results:
                # Extract the actual label name from the field_description dictionary
                label_name = field_description.get('en_US') if isinstance(field_description,
                                                                          dict) else field_description
                partner = mapper_model.search([('label_name', '=', column_name), ('system_name', '=', system_odoo)],
                                              limit=1)
                odoo_field_vals = {'label_name': column_name, 'field_type': data_type, 'internal_name': label_name,
                                   'pipedrive_instance_name': instance_name,
                                   'system_name': system_odoo}
                if not partner:
                    count += 1
                    mapper_model.create(odoo_field_vals)

                else:
                    count += 1
                    partner.write(odoo_field_vals)

            # Fetch pipedrive fields from the external API
            api_token = pipedrive_instances.api_token if 'api_token' in pipedrive_instances else None
            endpoint = f'{self.__API_BASE_URL}{field_name}?archive=false&api_token={api_token}'
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            payload_rec = {}

            # Make a GET request to the API endpoint
            response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")
            response.raise_for_status()

            if response.status_code == 200:
                data = response.json().get('data', [])

                # Store or update fetched pipedrive fields from the API in the mapper model
                for item in data:
                    label_name = item.get('name')
                    field_type = item.get('field_type')
                    internal_name = item.get('key')
                    field_id = item.get('id')
                    system_pipedrive = 'pipedrive'

                    partner = mapper_model.search(
                        [('label_name', '=', label_name), ('system_name', '=', system_pipedrive)],
                        limit=1)
                    pipedrive_field_vals = {'label_name': label_name, 'field_type': field_type,
                                            'pipedrive_instance_name': instance_name, 'system_name': system_pipedrive,
                                            'internal_name': internal_name, 'field_id': field_id,'field_definition': item}
                    if not partner:
                        count += 1
                        mapper_model.create(pipedrive_field_vals)
                    else:
                        count += 1
                        partner.write(pipedrive_field_vals)
                        partner.env.cr.commit()
                if logger_name != 'activity':
                    self.create_opd_field_mapping(table_name, logger_name, mapper_model, mapper_id_field,
                                                 mapper_lines_field)
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive {logger_name} fields"
                self.http_log_error(error_details, logger_name, description, payload_rec, response.text, '', 'manually', '',
                                    f"HTTP {response.status_code}")

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching {logger_name} fields'
            self.exception_log_error(error_details, logger_name, description, 'odoo', 'manually', '', error_type)
            return -1
            # Return -1 to indicate an error occurred

        return count
        # Return the total count of fields created or updated

    # --------------------- Create Automatic Field Mapping ---------------------- #

    def create_opd_field_mapping(self, table_name, logger_name, mapper_model, mapper_id_field,
                                mapper_lines_field):
        """
        Automatically map static fields for the Account module in oz.coa.lines.
        """
        # Initialize dropdown mapping containers before the loop
        odoo_company_dropdown_mapping = {}
        pipedrive_company_dropdown_mapping = {}

        odoo_contacts_dropdown_mapping = {}
        pipedrive_contacts_dropdown_mapping = {}

        odoo_deal_dropdown_mapping = {}
        pipedrive_deal_dropdown_mapping = {}

        odoo_lead_dropdown_mapping = {}
        pipedrive_lead_dropdown_mapping = {}

        odoo_product_dropdown_mapping = {}
        pipedrive_product_dropdown_mapping = {}

        instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        # Define static mappings for each model
        static_mappings_dict = {
            'company': [
                {'odoo_fields_record': 'name', 'pipedrive_fields_record': 'name'},
                {'odoo_fields_record': 'street', 'pipedrive_fields_record': 'address'},
                {'odoo_fields_record': 'country_id', 'pipedrive_fields_record': 'address_country'},
                {'odoo_fields_record': 'state_id', 'pipedrive_fields_record': 'address_admin_area_level_1'},
                {'odoo_fields_record': 'city', 'pipedrive_fields_record': 'address_locality'},
                {'odoo_fields_record': 'zip', 'pipedrive_fields_record': 'address_postal_code'},
                {'odoo_fields_record': 'sync_to_pipedrive', 'pipedrive_fields_record': 'sync_to_odoo'},
            ],
            'contact': [
                {'odoo_fields_record': 'name', 'pipedrive_fields_record': 'name'},
                {'odoo_fields_record': 'email', 'pipedrive_fields_record': 'email'},
                {'odoo_fields_record': 'phone', 'pipedrive_fields_record': 'phone'},
                {'odoo_fields_record': 'sync_to_pipedrive', 'pipedrive_fields_record': 'sync_to_odoo'},
            ],
            'lead': [
                {'odoo_fields_record': 'name', 'pipedrive_fields_record': 'title'},
                {'odoo_fields_record': 'source_id', 'pipedrive_fields_record': 'channel'},
                {'odoo_fields_record': 'sync_to_pipedrive', 'pipedrive_fields_record': 'sync_to_odoo'},
            ],
            'deal': [
                {'odoo_fields_record': 'name', 'pipedrive_fields_record': 'title'},
                {'odoo_fields_record': 'expected_revenue', 'pipedrive_fields_record': 'value'},
                {'odoo_fields_record': 'probability', 'pipedrive_fields_record': 'probability'},
                {'odoo_fields_record': 'date_deadline', 'pipedrive_fields_record': 'expected_close_date'},
                {'odoo_fields_record': 'stage_id', 'pipedrive_fields_record': 'stage_id'},
                {'odoo_fields_record': 'sync_to_pipedrive', 'pipedrive_fields_record': 'sync_to_odoo'},
            ],
            'product': [
                {'odoo_fields_record': 'name', 'pipedrive_fields_record': 'name'},
                {'odoo_fields_record': 'list_price', 'pipedrive_fields_record': 'price'},
                {'odoo_fields_record': 'categ_id', 'pipedrive_fields_record': 'category'},
                {'odoo_fields_record': 'description', 'pipedrive_fields_record': 'description'},
                {'odoo_fields_record': 'default_code', 'pipedrive_fields_record': 'code'},
                {'odoo_fields_record': 'sync_to_pipedrive', 'pipedrive_fields_record': 'sync_to_odoo'},
            ]
        }

        # Fetch the static mappings for the model
        static_mappings = static_mappings_dict.get(logger_name, [])

        # Loop through static mappings and create field mappings
        for mapping in static_mappings:
            # Find Odoo and Pipedrive field labels in the mapper model
            odoo_field = mapper_model.search(
                [('label_name', '=', mapping['odoo_fields_record']), ('system_name', '=', 'Odoo')], limit=1)
            # For dynamic 'sync_to_odoo' mapping
            if mapping['pipedrive_fields_record'] == 'sync_to_odoo':
                pipedrive_field = mapper_model.search(
                    [('label_name', '=', 'sync_to_odoo'), ('system_name', '=', 'pipedrive')], limit=1)
            else:
                pipedrive_field = mapper_model.search(
                    [('internal_name', '=', mapping['pipedrive_fields_record']), ('system_name', '=', 'pipedrive')],
                    limit=1)

            # Check if both fields exist
            if odoo_field and pipedrive_field:
                field_mapping_record = self.env[mapper_lines_field].search(
                    [('odoo_fields_record', '=', odoo_field.id), ('pipedrive_fields_record', '=', pipedrive_field.id),
                     ], limit=1)
                # Create a new field mapping in oz.coa.lines
                if not field_mapping_record:
                    field_mapping_record = self.env[mapper_lines_field].create({
                        'odoo_fields_record': odoo_field.id,
                        'pipedrive_fields_record': pipedrive_field.id,
                        mapper_id_field: instance_id.id
                    })
                    field_mapping_record.env.cr.commit()
                if pipedrive_field.label_name == 'sync_to_odoo':
                    odoo_map, pipedrive_map = self._generate_dropdown_mapping(pipedrive_field, 'sync_to_odoo')
                    if logger_name == 'company':
                        odoo_company_dropdown_mapping.update(odoo_map)
                        instance_id.odoo_company_dropdown_mapping = json.dumps(odoo_company_dropdown_mapping, indent=4)
                        pipedrive_company_dropdown_mapping.update(pipedrive_map)
                        instance_id.pipedrive_company_dropdown_mapping = json.dumps(pipedrive_company_dropdown_mapping, indent=4)
                    elif logger_name == 'contact':
                        odoo_contacts_dropdown_mapping.update(odoo_map)
                        instance_id.odoo_contacts_dropdown_mapping = json.dumps(odoo_contacts_dropdown_mapping, indent=4)
                        pipedrive_contacts_dropdown_mapping.update(pipedrive_map)
                        instance_id.pipedrive_contacts_dropdown_mapping = json.dumps(pipedrive_contacts_dropdown_mapping, indent=4)
                    elif logger_name == 'deal':
                        odoo_deal_dropdown_mapping.update(odoo_map)
                        pipedrive_deal_dropdown_mapping.update(pipedrive_map)
                        self._apply_deal_dropdown_mapping(
                            instance_id, odoo_deal_dropdown_mapping, pipedrive_deal_dropdown_mapping
                        )
                        instance_id.odoo_deal_dropdown_mapping = json.dumps(odoo_deal_dropdown_mapping, indent=4)
                        instance_id.pipedrive_deal_dropdown_mapping = json.dumps(pipedrive_deal_dropdown_mapping, indent=4)
                    elif logger_name == 'lead':
                        odoo_lead_dropdown_mapping.update(odoo_map)
                        pipedrive_lead_dropdown_mapping.update(pipedrive_map)
                        self._apply_lead_dropdown_mapping(
                            instance_id, odoo_lead_dropdown_mapping, pipedrive_lead_dropdown_mapping
                        )
                        instance_id.odoo_lead_dropdown_mapping = json.dumps(odoo_lead_dropdown_mapping, indent=4)
                        instance_id.pipedrive_lead_dropdown_mapping = json.dumps(pipedrive_lead_dropdown_mapping, indent=4)
                    elif logger_name == 'product':
                        odoo_product_dropdown_mapping.update(odoo_map)
                        pipedrive_product_dropdown_mapping.update(pipedrive_map)
                        instance_id.odoo_product_dropdown_mapping = json.dumps(odoo_product_dropdown_mapping, indent=4)
                        instance_id.pipedrive_product_dropdown_mapping = json.dumps(pipedrive_product_dropdown_mapping, indent=4)

    # ------------------- Generate Dropdown mapping -------------------- #

    def _generate_dropdown_mapping(self, pipedrive_field, dropdown_field_label):
        """
        Generate dropdown mapping from Pipedrive field metadata.

        :param pipedrive_field: recordset of pipedrive field (from mapper_model)
        :param dropdown_field_label: str, internal name like 'sync_to_odoo'
        :return: (odoo_map, pipedrive_map) as dictionaries
        """
        odoo_map = {}
        pipedrive_map = {}

        if not pipedrive_field or pipedrive_field.label_name != dropdown_field_label:
            return odoo_map, pipedrive_map

        pipedrive_internal_name = pipedrive_field.internal_name
        if not pipedrive_internal_name:
            return odoo_map, pipedrive_map

        field_metadata_dict = pipedrive_field.field_definition

        if isinstance(field_metadata_dict, str):
            field_metadata_dict = self._parse_pipedrive_field_metadata(field_metadata_dict)
            if not field_metadata_dict:
                _logger.error(f"Failed to parse field_definition for {dropdown_field_label}")
                return odoo_map, pipedrive_map

        options = field_metadata_dict.get('options', [])

        for option in options:
            label = option.get('label', '').lower()
            option_id = str(option.get('id'))

            if label == 'yes':
                odoo_map["yes"] = option_id
                pipedrive_map[option_id] = "yes"
            elif label == 'no':
                odoo_map["no"] = option_id
                pipedrive_map[option_id] = "no"

        return {"sync_to_pipedrive": odoo_map}, {pipedrive_internal_name: pipedrive_map}

    @api.model
    def _is_odoo_lost_stage(self, stage):
        if stage.is_won:
            return False
        name = (stage.name or '').strip().lower()
        return name in {'lost', 'closed lost', 'closed-lost'} or stage.fold

    @api.model
    def _get_odoo_regular_stages(self, team=None):
        """CRM stages used for open deals, optionally scoped to a sales team."""
        domain = []
        if team:
            domain = ['|', ('team_ids', '=', False), ('team_ids', 'in', team.ids)]
        stages = self.env['crm.stage'].search(domain, order='sequence, id')
        return stages.filtered(lambda s: not s.is_won and not self._is_odoo_lost_stage(s))

    @api.model
    def _fetch_pipedrive_v2_collection(self, instance_id, resource, extra_params=None):
        """Fetch all records from a Pipedrive v2 collection endpoint (cursor pagination)."""
        api_base_url = self.get_validated_api_base_url(instance_id, 'deal', 'manually')
        api_token = instance_id.api_token
        if not api_base_url or not api_token:
            return None

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'API Key {api_token}',
        }
        params = {'limit': 500}
        if extra_params:
            params.update(extra_params)

        all_records = []
        cursor = None
        while True:
            query = '&'.join(f'{key}={value}' for key, value in params.items())
            endpoint = f'{api_base_url}/{resource}?{query}&api_token={api_token}'
            if cursor:
                endpoint += f'&cursor={cursor}'
            response = self.fetch_data(endpoint, headers, {}, method='GET')
            if response.status_code != 200:
                _logger.warning(
                    'Pipedrive v2 %s fetch failed (%s): %s',
                    resource, response.status_code, response.text,
                )
                return None
            body = response.json()
            all_records.extend(body.get('data') or [])
            cursor = (body.get('additional_data') or {}).get('next_cursor')
            if not cursor:
                break
        return all_records

    @api.model
    def _fetch_pipedrive_v1_collection(self, instance_id, resource, extra_params=None):
        """Fallback fetch for v1 endpoints when api_base_url is not configured."""
        api_token = instance_id.api_token
        if not api_token:
            return None

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'API Key {api_token}',
        }
        all_records = []
        start = 0
        limit = 500
        while True:
            params = {'start': start, 'limit': limit, 'api_token': api_token}
            if extra_params:
                params.update(extra_params)
            query = '&'.join(f'{key}={value}' for key, value in params.items())
            endpoint = f'{self.__API_BASE_URL}{resource}?{query}'
            response = self.fetch_data(endpoint, headers, {}, method='GET')
            if response.status_code != 200:
                _logger.warning(
                    'Pipedrive v1 %s fetch failed (%s): %s',
                    resource, response.status_code, response.text,
                )
                return None
            body = response.json()
            batch = body.get('data') or []
            if not batch:
                break
            all_records.extend(batch)
            if not body.get('additional_data', {}).get('pagination', {}).get('more_items_in_collection'):
                break
            start += limit
        return all_records

    @api.model
    def _fetch_pipedrive_v1_field_by_id(self, instance_id, resource, field_id):
        """Fetch a single v1 field definition (includes enum options when present)."""
        api_token = instance_id.api_token
        if not api_token or not field_id:
            return []
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'API Key {api_token}',
        }
        endpoint = f'{self.__API_BASE_URL}{resource}/{field_id}?api_token={api_token}'
        response = self.fetch_data(endpoint, headers, {}, method='GET')
        if response.status_code != 200:
            _logger.warning(
                'Pipedrive v1 %s/%s fetch failed (%s): %s',
                resource, field_id, response.status_code, response.text,
            )
            return []
        field = (response.json() or {}).get('data') or {}
        return self._extract_options_from_pipedrive_field(field)

    @api.model
    def _fetch_pipedrive_stages_and_pipelines(self, instance_id):
        """Fetch stages and pipelines using v2 API (same as deals); fall back to v1."""
        api_base_url = (instance_id.api_base_url or '').strip().rstrip('/')
        if api_base_url:
            pipelines = self._fetch_pipedrive_v2_collection(instance_id, 'pipelines')
            stages = self._fetch_pipedrive_v2_collection(
                instance_id, 'stages', {'sort_by': 'order_nr', 'sort_direction': 'asc'}
            )
            if pipelines is not None and stages is not None:
                return stages, pipelines, 'v2'

        pipelines = self._fetch_pipedrive_v1_collection(instance_id, 'pipelines')
        stages = self._fetch_pipedrive_v1_collection(instance_id, 'stages')
        if pipelines is None or stages is None:
            return None, None, None
        return stages, pipelines, 'v1'

    @api.model
    def _sort_pipedrive_stages(self, pipedrive_stages):
        active_stages = [
            stage for stage in pipedrive_stages
            if stage.get('id') and not stage.get('is_deleted')
        ]
        if any(stage.get('order_nr') is not None for stage in active_stages):
            return sorted(active_stages, key=lambda stage: (stage.get('order_nr') or 0, stage.get('id')))
        return sorted(active_stages, key=lambda stage: stage.get('id') or 0)

    @api.model
    def _map_pipeline_stages(self, pipedrive_stages, odoo_stages, pipedrive_stage_to_odoo,
                             odoo_stage_to_pipedrive, unmatched_pipedrive_stages):
        """
        Map Pipedrive stages to Odoo stages for one pipeline.
        1) exact name match, 2) positional match by pipeline order vs Odoo sequence.
        """
        sorted_pipedrive_stages = self._sort_pipedrive_stages(pipedrive_stages)
        regular_odoo_stages = odoo_stages.sorted(key=lambda stage: (stage.sequence, stage.id))
        odoo_by_name = {
            (stage.name or '').strip().lower(): stage
            for stage in regular_odoo_stages if (stage.name or '').strip()
        }
        matched_odoo_ids = set()
        unmatched_pipedrive = []

        for pipedrive_stage in sorted_pipedrive_stages:
            stage_id = pipedrive_stage.get('id')
            stage_name = (pipedrive_stage.get('name') or '').strip()
            name_key = stage_name.lower()
            odoo_stage = odoo_by_name.get(name_key)
            if odoo_stage and odoo_stage.id not in matched_odoo_ids:
                pipedrive_stage_to_odoo[str(stage_id)] = odoo_stage.id
                odoo_stage_to_pipedrive[str(odoo_stage.id)] = stage_id
                matched_odoo_ids.add(odoo_stage.id)
            else:
                unmatched_pipedrive.append(pipedrive_stage)

        remaining_odoo = [
            stage for stage in regular_odoo_stages if stage.id not in matched_odoo_ids
        ]
        for pipedrive_stage, odoo_stage in zip(unmatched_pipedrive, remaining_odoo):
            stage_id = pipedrive_stage.get('id')
            pipedrive_stage_to_odoo[str(stage_id)] = odoo_stage.id
            odoo_stage_to_pipedrive[str(odoo_stage.id)] = stage_id
            matched_odoo_ids.add(odoo_stage.id)

        for pipedrive_stage in unmatched_pipedrive[len(remaining_odoo):]:
            stage_name = (pipedrive_stage.get('name') or '').strip()
            if stage_name:
                unmatched_pipedrive_stages.append(stage_name)

    @api.model
    def _find_odoo_won_lost_stages(self, odoo_stages):
        """Return (won_stage, lost_stage) recordsets from Odoo CRM stages."""
        won_stage = self.env['crm.stage']
        lost_stage = self.env['crm.stage']
        won_names = {'won', 'closed won', 'closed-won'}
        lost_names = {'lost', 'closed lost', 'closed-lost'}

        for stage in odoo_stages:
            name = (stage.name or '').strip().lower()
            if hasattr(stage, 'is_won') and stage.is_won:
                won_stage = stage
            elif name in won_names:
                won_stage = stage
            elif name in lost_names:
                lost_stage = stage

        if not won_stage:
            won_stage = odoo_stages.filtered(
                lambda s: s.name and 'won' in s.name.lower()
            )[:1]
        if not lost_stage:
            lost_stage = odoo_stages.filtered(
                lambda s: s.name and 'lost' in s.name.lower()
            )[:1]
        return won_stage, lost_stage

    @api.model
    def _build_deal_stage_pipeline_dropdown_mapping(self, instance_id):
        """
        Build stage_id and pipeline_id dropdown mappings from live Pipedrive data.
        Uses Pipedrive v2 stages/pipelines API (same as deals sync), with v1 fallback.
        Maps by stage name first, then by pipeline order vs Odoo stage sequence.
        """
        api_token = instance_id.api_token
        if not api_token:
            return None

        pipedrive_stages, pipedrive_pipelines, api_version = self._fetch_pipedrive_stages_and_pipelines(
            instance_id
        )
        if pipedrive_stages is None or pipedrive_pipelines is None:
            return None

        odoo_stages = self.env['crm.stage'].search([])
        odoo_teams = self.env['crm.team'].search([])
        odoo_team_by_name = {
            (team.name or '').strip().lower(): team
            for team in odoo_teams if (team.name or '').strip()
        }

        pipedrive_stage_to_odoo = {}
        odoo_stage_to_pipedrive = {}
        unmatched_pipedrive_stages = []
        pipedrive_pipeline_to_odoo = {}
        unmatched_pipelines = []

        stages_by_pipeline = {}
        for pipedrive_stage in pipedrive_stages:
            pipeline_id = pipedrive_stage.get('pipeline_id')
            if pipeline_id is None:
                continue
            stages_by_pipeline.setdefault(pipeline_id, []).append(pipedrive_stage)

        single_pipeline_fallback = len(pipedrive_pipelines) == 1
        single_team_fallback = len(odoo_teams) == 1

        for pipedrive_pipeline in pipedrive_pipelines:
            pipeline_id = pipedrive_pipeline.get('id')
            if not pipeline_id:
                continue
            pipeline_name = (pipedrive_pipeline.get('name') or '').strip()
            odoo_team = odoo_team_by_name.get(pipeline_name.lower())
            if not odoo_team and single_pipeline_fallback and single_team_fallback:
                odoo_team = odoo_teams[:1]
            if odoo_team:
                pipedrive_pipeline_to_odoo[str(pipeline_id)] = odoo_team.id
            elif pipeline_name:
                unmatched_pipelines.append(pipeline_name)

            pipeline_stages = stages_by_pipeline.get(pipeline_id, [])
            odoo_regular_stages = self._get_odoo_regular_stages(odoo_team)
            if not odoo_regular_stages:
                odoo_regular_stages = self._get_odoo_regular_stages()
            self._map_pipeline_stages(
                pipeline_stages,
                odoo_regular_stages,
                pipedrive_stage_to_odoo,
                odoo_stage_to_pipedrive,
                unmatched_pipedrive_stages,
            )

        # Stages without pipeline_id (safety net)
        orphan_stages = [
            stage for stage in pipedrive_stages
            if stage.get('id') and stage.get('pipeline_id') is None and not stage.get('is_deleted')
        ]
        if orphan_stages:
            self._map_pipeline_stages(
                orphan_stages,
                self._get_odoo_regular_stages(),
                pipedrive_stage_to_odoo,
                odoo_stage_to_pipedrive,
                unmatched_pipedrive_stages,
            )

        won_stage, lost_stage = self._find_odoo_won_lost_stages(odoo_stages)
        if won_stage:
            pipedrive_stage_to_odoo['won'] = won_stage.id
            odoo_stage_to_pipedrive[str(won_stage.id)] = 'won'
        if lost_stage:
            pipedrive_stage_to_odoo['lost'] = lost_stage.id
            odoo_stage_to_pipedrive[str(lost_stage.id)] = 'lost'

        mapped_stage_count = sum(
            1 for key in pipedrive_stage_to_odoo if key not in ('won', 'lost')
        )
        total_pipedrive_stages = len([
            stage for stage in pipedrive_stages
            if stage.get('id') and not stage.get('is_deleted')
        ])

        return {
            'odoo': {
                'stage_id': odoo_stage_to_pipedrive,
            },
            'pipedrive': {
                'stage_id': pipedrive_stage_to_odoo,
                'pipeline_id': pipedrive_pipeline_to_odoo,
            },
            'unmatched_stages': unmatched_pipedrive_stages,
            'unmatched_pipelines': unmatched_pipelines,
            'mapped_stage_count': mapped_stage_count,
            'total_pipedrive_stages': total_pipedrive_stages,
            'api_version': api_version,
        }

    @api.model
    def _apply_deal_dropdown_mapping(self, instance_id, odoo_deal_dropdown_mapping, pipedrive_deal_dropdown_mapping):
        """Merge auto-generated deal stage/pipeline maps into dropdown mapping dicts."""
        stage_pipeline_maps = self._build_deal_stage_pipeline_dropdown_mapping(instance_id)
        if not stage_pipeline_maps:
            return stage_pipeline_maps
        odoo_deal_dropdown_mapping.update(stage_pipeline_maps['odoo'])
        pipedrive_deal_dropdown_mapping.update(stage_pipeline_maps['pipedrive'])
        return stage_pipeline_maps

    @api.model
    def _parse_pipedrive_field_metadata(self, raw):
        """Parse stored/API Pipedrive field metadata (dict, JSON, or Python repr)."""
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}
        stripped = raw.strip()
        if not stripped:
            return {}
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
        return {}

    @api.model
    def _find_pipedrive_field_in_list(self, fields_list, field_keys, label_names=None):
        """Find a Pipedrive field by key/field_code and optional display name."""
        keys_lower = {str(key).lower() for key in (field_keys or [])}
        labels = {name.strip().lower() for name in (label_names or []) if name}
        for field in fields_list or []:
            key = field.get('key') or field.get('field_code') or field.get('name')
            if key and str(key).lower() in keys_lower:
                return field
            display_name = (field.get('name') or field.get('title') or '').strip().lower()
            if display_name in labels:
                return field
        return None

    @api.model
    def _extract_options_from_pipedrive_field(self, field_data):
        """Extract [{id, label}, ...] from a Pipedrive field definition."""
        field_data = self._parse_pipedrive_field_metadata(field_data)
        if not field_data:
            return []
        options = field_data.get('options') or []
        extracted = []
        for option in options:
            option_id = option.get('id')
            if option_id in (None, False, ''):
                continue
            label = (option.get('label') or option.get('name') or '').strip()
            extracted.append({'id': option_id, 'label': label})
        return extracted

    @api.model
    def _fetch_pipedrive_v2_field_options(self, instance_id, resource, field_code):
        """Fetch enum/set options for a v2 field (options are not always on the field list)."""
        api_base_url = self.get_validated_api_base_url(instance_id, 'product', 'manually')
        api_token = instance_id.api_token
        if not api_base_url or not api_token or not field_code:
            return []

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'API Key {api_token}',
        }
        all_options = []
        cursor = None
        while True:
            endpoint = (
                f'{api_base_url}/{resource}/{field_code}/options'
                f'?limit=500&api_token={api_token}'
            )
            if cursor:
                endpoint += f'&cursor={cursor}'
            response = self.fetch_data(endpoint, headers, {}, method='GET')
            if response.status_code != 200:
                _logger.warning(
                    'Pipedrive v2 %s/%s/options fetch failed (%s): %s',
                    resource, field_code, response.status_code, response.text,
                )
                return []
            body = response.json()
            all_options.extend(body.get('data') or [])
            cursor = (body.get('additional_data') or {}).get('next_cursor')
            if not cursor:
                break
        return self._extract_options_from_pipedrive_field({'options': all_options})

    @api.model
    def _get_pipedrive_enum_field_options(self, instance_id, v1_endpoint, v2_resource, field_keys,
                                          label_names=None):
        """
        Load enum options for a Pipedrive field.
        v1 field metadata includes options inline; v2 requires /{field_code}/options.
        """
        label_names = set(label_names or [])
        label_names.update(str(key) for key in (field_keys or []))
        label_names.update(name.title() for name in list(label_names))

        # v1 first — same archive=false flag as Import Product Fields
        v1_fields = self._fetch_pipedrive_v1_collection(
            instance_id, v1_endpoint, extra_params={'archive': 'false'}
        )
        if v1_fields:
            field = self._find_pipedrive_field_in_list(v1_fields, field_keys, label_names)
            if field:
                options = self._extract_options_from_pipedrive_field(field)
                if not options and v2_resource:
                    field_code = field.get('field_code') or field.get('key')
                    options = self._fetch_pipedrive_v2_field_options(
                        instance_id, v2_resource, field_code
                    )
                if not options and field.get('id'):
                    options = self._fetch_pipedrive_v1_field_by_id(
                        instance_id, v1_endpoint, field.get('id')
                    )
                if options:
                    return options, 'v1'

        if v2_resource:
            v2_fields = self._fetch_pipedrive_v2_collection(instance_id, v2_resource)
            if v2_fields:
                field = self._find_pipedrive_field_in_list(v2_fields, field_keys, label_names)
                if field:
                    options = self._extract_options_from_pipedrive_field(field)
                    if not options:
                        field_code = field.get('field_code') or field.get('key')
                        options = self._fetch_pipedrive_v2_field_options(
                            instance_id, v2_resource, field_code
                        )
                    if options:
                        return options, 'v2'

        return None, None

    @api.model
    def _get_enum_options_from_mapper(self, instance_id, mapper_model, internal_name, label_names=None):
        """Fallback: read enum options from imported Pipedrive field mapper records."""
        label_names = list(label_names or [])
        instance_name = instance_id.name if instance_id else False
        domain = [('system_name', '=', 'pipedrive')]
        if instance_name:
            domain.append(('pipedrive_instance_name', '=', instance_name))

        search_domains = []
        if internal_name:
            search_domains.append(domain + [('internal_name', '=', internal_name)])
            search_domains.append(domain + [('internal_name', 'ilike', internal_name)])
        for label in label_names:
            search_domains.append(domain + [('label_name', 'ilike', label)])

        seen_ids = set()
        candidates = self.env[mapper_model]
        for search_domain in search_domains:
            for field in self.env[mapper_model].search(search_domain):
                if field.id in seen_ids:
                    continue
                seen_ids.add(field.id)
                candidates |= field

        for field in candidates:
            options = self._extract_options_from_pipedrive_field(field.field_definition)
            if options:
                return options
            if field.field_id:
                endpoint = {
                    'opd.productmapper': 'productFields',
                    'opd.leadmapper': 'dealFields',
                    'opd.dealmapper': 'dealFields',
                }.get(mapper_model, 'productFields')
                options = self._fetch_pipedrive_v1_field_by_id(instance_id, endpoint, field.field_id)
                if options:
                    return options
        return None

    @api.model
    def _get_enum_options_from_instance_field_lines(self, instance_id, lines_field_name, odoo_field_name,
                                                    v1_endpoint):
        """Read enum options from the instance field-mapping line for an Odoo field."""
        lines = getattr(instance_id, lines_field_name, self.env['pipedriveinstance.products.lines'])
        for line in lines:
            odoo_mapper = line.odoo_fields_record
            if not odoo_mapper or odoo_mapper.label_name != odoo_field_name:
                continue
            pipedrive_mapper = line.pipedrive_fields_record
            if not pipedrive_mapper:
                continue
            options = self._extract_options_from_pipedrive_field(pipedrive_mapper.field_definition)
            if options:
                return options
            if pipedrive_mapper.field_id:
                options = self._fetch_pipedrive_v1_field_by_id(
                    instance_id, v1_endpoint, pipedrive_mapper.field_id
                )
                if options:
                    return options
        return None

    @api.model
    def _fetch_pipedrive_field_metadata_list(self, instance_id, v1_endpoint, v2_resource=None):
        """Fetch Pipedrive field metadata from v1 (preferred) or v2."""
        v1_fields = self._fetch_pipedrive_v1_collection(instance_id, v1_endpoint)
        if v1_fields:
            return v1_fields, 'v1'
        if v2_resource:
            v2_fields = self._fetch_pipedrive_v2_collection(instance_id, v2_resource)
            if v2_fields is not None:
                return v2_fields, 'v2'
        return None, None

    @api.model
    def _build_dropdown_mapping_by_name_and_order(self, pipedrive_options, odoo_records, odoo_order='id'):
        """
        Map Pipedrive enum options to Odoo records.
        1) exact name match, 2) positional match by option id vs Odoo record order.
        """
        pipedrive_map = {}
        odoo_map = {}
        unmatched_labels = []
        if not pipedrive_options:
            return odoo_map, pipedrive_map, unmatched_labels

        if odoo_order == 'sequence':
            sorted_odoo = odoo_records.sorted(key=lambda record: (record.sequence, record.id))
        else:
            sorted_odoo = odoo_records.sorted(key=lambda record: record.id)

        odoo_by_name = {
            (record.name or '').strip().lower(): record
            for record in sorted_odoo if (record.name or '').strip()
        }
        matched_odoo_ids = set()
        unmatched_options = []
        sorted_options = sorted(pipedrive_options, key=lambda option: option.get('id') or 0)

        for option in sorted_options:
            option_id = option.get('id')
            label_key = (option.get('label') or '').strip().lower()
            odoo_record = odoo_by_name.get(label_key) if label_key else None
            if odoo_record and odoo_record.id not in matched_odoo_ids:
                pipedrive_map[str(option_id)] = odoo_record.id
                odoo_map[str(odoo_record.id)] = option_id
                matched_odoo_ids.add(odoo_record.id)
            else:
                unmatched_options.append(option)

        remaining_odoo = [
            record for record in sorted_odoo if record.id not in matched_odoo_ids
        ]
        for option, odoo_record in zip(unmatched_options, remaining_odoo):
            option_id = option.get('id')
            pipedrive_map[str(option_id)] = odoo_record.id
            odoo_map[str(odoo_record.id)] = option_id
            matched_odoo_ids.add(odoo_record.id)

        for option in unmatched_options[len(remaining_odoo):]:
            label = (option.get('label') or '').strip()
            if label:
                unmatched_labels.append(label)

        return odoo_map, pipedrive_map, unmatched_labels

    @api.model
    def _build_lead_channel_dropdown_mapping(self, instance_id):
        """
        Build source_id/channel dropdown mappings from Pipedrive channel options.
        Channel allowed values are published on dealFields (per Pipedrive API).
        """
        options, api_version = self._get_pipedrive_enum_field_options(
            instance_id, 'dealFields', 'dealFields', {'channel'}, {'channel', 'Channel'}
        )
        if not options:
            options, api_version = self._get_pipedrive_enum_field_options(
                instance_id, 'leadFields', None, {'channel'}, {'channel', 'Channel'}
            )
        if not options:
            options = self._get_enum_options_from_instance_field_lines(
                instance_id, 'leads_line_ids', 'source_id', 'dealFields'
            )
            if options:
                api_version = 'instance_mapping'
        if not options:
            options = self._get_enum_options_from_mapper(
                instance_id, 'opd.leadmapper', 'channel', {'channel', 'Channel'}
            )
            if options:
                api_version = 'mapper'

        if not options:
            return None

        odoo_sources = self.env['utm.source'].search([], order='id')
        odoo_map, pipedrive_map, unmatched = self._build_dropdown_mapping_by_name_and_order(
            options, odoo_sources
        )
        return {
            'odoo': {'source_id': odoo_map},
            'pipedrive': {'channel': pipedrive_map},
            'unmatched': unmatched,
            'mapped_count': len(pipedrive_map),
            'total_count': len(options),
            'api_version': api_version,
        }

    @api.model
    def _build_product_category_dropdown_mapping(self, instance_id):
        """Build categ_id/category dropdown mappings from Pipedrive product category options."""
        options, api_version = self._get_pipedrive_enum_field_options(
            instance_id, 'productFields', 'productFields', {'category'}, {'category', 'Category'}
        )
        if not options:
            options = self._get_enum_options_from_instance_field_lines(
                instance_id, 'products_line_ids', 'categ_id', 'productFields'
            )
            if options:
                api_version = 'instance_mapping'
        if not options:
            options = self._get_enum_options_from_mapper(
                instance_id, 'opd.productmapper', 'category', {'category', 'Category'}
            )
            if options:
                api_version = 'mapper'

        if not options:
            return None

        odoo_categories = self.env['product.category'].search([], order='id')
        odoo_map, pipedrive_map, unmatched = self._build_dropdown_mapping_by_name_and_order(
            options, odoo_categories
        )
        return {
            'odoo': {'categ_id': odoo_map},
            'pipedrive': {'category': pipedrive_map},
            'unmatched': unmatched,
            'mapped_count': len(pipedrive_map),
            'total_count': len(options),
            'api_version': api_version,
        }

    @api.model
    def _apply_lead_dropdown_mapping(self, instance_id, odoo_lead_dropdown_mapping, pipedrive_lead_dropdown_mapping):
        """Merge auto-generated lead channel maps into dropdown mapping dicts."""
        channel_maps = self._build_lead_channel_dropdown_mapping(instance_id)
        if not channel_maps:
            return channel_maps
        odoo_lead_dropdown_mapping.update(channel_maps['odoo'])
        pipedrive_lead_dropdown_mapping.update(channel_maps['pipedrive'])
        return channel_maps

    @api.model
    def _apply_product_dropdown_mapping(self, instance_id, odoo_product_dropdown_mapping, pipedrive_product_dropdown_mapping):
        """Merge auto-generated product category maps into dropdown mapping dicts."""
        category_maps = self._build_product_category_dropdown_mapping(instance_id)
        if not category_maps:
            return category_maps
        odoo_product_dropdown_mapping.update(category_maps['odoo'])
        pipedrive_product_dropdown_mapping.update(category_maps['pipedrive'])
        return category_maps

    # ------------------------------ Return Response Method ---------------------------- #
    @api.model
    def fetch_data(self, url, headers, payload, method="POST"):
        """
        Fetches data from the specified URL using the specified method.

        Args:
            url (str): The URL to fetch data from.
            headers (dict): The headers to include in the request.
            payload (dict): The payload data to include in the request.
            method (str, optional): The HTTP method to use for the request. Defaults to "POST".

        Returns:
            requests.Response: The response object.
        """
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, data=payload)
        elif method.upper() == "GET":
            response = requests.get(url, headers=headers, params=payload)
        else:
            raise ValueError("Invalid HTTP method. Supported methods are 'GET' and 'POST'.")

        return response

    # ------------------------- Pipedrive Required Custom Fields -------------------------- #

    @api.model
    def _normalize_pipedrive_record(self, record):
        if isinstance(record, list):
            return record[0] if record else {}
        return record or {}

    @api.model
    def _get_pipedrive_custom_field_value(self, record, field_key):
        """Safely read a mapped custom field from a Pipedrive record (v1 or v2)."""
        record_data = self._normalize_pipedrive_record(record)
        if not field_key:
            return None
        custom_fields = record_data.get('custom_fields') or {}
        if isinstance(custom_fields, dict) and field_key in custom_fields:
            return custom_fields.get(field_key)
        return record_data.get(field_key)

    @api.model
    def _extract_pipedrive_owner_id(self, owner_ref):
        if owner_ref is None:
            return None
        if isinstance(owner_ref, dict):
            owner_ref = owner_ref.get('id') or owner_ref.get('value')
        if owner_ref in (None, False, ''):
            return None
        try:
            return int(owner_ref)
        except (TypeError, ValueError):
            return None

    @api.model
    def _get_pipedrive_owner_ref_from_record(self, record, primary_key='owner_id'):
        """Read owner reference from a Pipedrive record without raising on missing keys."""
        record_data = self._normalize_pipedrive_record(record)
        if not record_data:
            return None

        keys = []
        if primary_key:
            keys.append(primary_key)
        for fallback_key in ('owner_id', 'user_id'):
            if fallback_key not in keys:
                keys.append(fallback_key)

        for key in keys:
            value = record_data.get(key)
            if value not in (None, False, ''):
                return value

        owner = record_data.get('owner')
        if isinstance(owner, dict):
            return owner.get('id') or owner.get('value')
        return None

    @api.model
    def get_odoo_user_from_pipedrive_record(self, record, owner_key='owner_id'):
        """
        Resolve a Pipedrive record owner to the matching Odoo internal user.
        Never raises when owner fields are missing (v1/v2 safe).
        """
        owner_ref = self._get_pipedrive_owner_ref_from_record(record, owner_key)
        owner_id = self._extract_pipedrive_owner_id(owner_ref)
        if not owner_id:
            return self.env['res.users']
        return self.env['res.users'].search(
            [('pipedrive_id', '=', owner_id), ('share', '=', False), ('active', '=', True)], limit=1
        )

    @api.model
    def get_validated_api_base_url(self, instance_id, logger_name, operation_type):
        api_base_url = (instance_id.api_base_url or '').strip().rstrip('/')
        if not api_base_url:
            description = _(
                'Pipedrive API Base URL is not configured. '
                'Please set it on the instance (e.g. https://yourcompany.pipedrive.com/api/v2).'
            )
            self.log_operation_warning(
                logger_name, description, _('Configuration Error'), 'pipedrive', {}, operation_type, ''
            )
            return None
        return api_base_url

    def _get_pipedrive_api_headers(self, api_token):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'API Key {api_token}',
        }

    def _fetch_pipedrive_custom_fields(self, api_token, endpoint):
        url = f'{self.__API_BASE_URL}{endpoint}?archive=false&api_token={api_token}'
        response = self.fetch_data(url, self._get_pipedrive_api_headers(api_token), {}, method="GET")
        if response.status_code != 200:
            return None, response
        return response.json().get('data', []) or [], response

    @api.model
    def _pipedrive_custom_field_exists(self, existing_fields, field_name):
        return any(field.get('name') == field_name for field in existing_fields)

    @api.model
    def _create_pipedrive_custom_field(self, api_token, endpoint, field_payload, logger_name, operation_type):
        url = f'{self.__API_BASE_URL}{endpoint}?api_token={api_token}'
        json_payload = json.dumps(field_payload)
        response = requests.post(
            url, headers=self._get_pipedrive_api_headers(api_token), data=json_payload
        )
        field_name = field_payload.get('name')
        if response.status_code in (200, 201):
            response_json = response.json()
            if response_json.get('success'):
                self.log_custom_field_operation(
                    logger_name, field_name, operation_type, response.status_code,
                    response_json.get('data'), log_type='success'
                )
                return 'created', response_json.get('data')
        error_details = f"{response.status_code} - {response.reason}"
        description = _("Failed to create Pipedrive custom field '%s'") % field_name
        self.log_custom_field_operation(
            logger_name, field_name, operation_type, error_details, field_payload,
            log_type='error', response_text=response.text
        )
        return 'error', None

    @api.model
    def log_custom_field_operation(self, logger_name, field_name, operation_type, status_code='',
                                   field_data=None, log_type='success', response_text=''):
        """Log custom field setup actions with entity-specific messages."""
        module_name, record_direction = self.get_module_and_direction(logger_name, 'pipedrive')
        entity_label = logger_name.capitalize()
        operation = _('Create Custom Field')
        request_payload = field_data if isinstance(field_data, dict) else {}
        response_payload = response_text or ''

        if log_type == 'success':
            field_key = ''
            if isinstance(field_data, dict):
                field_key = field_data.get('key') or field_data.get('id') or ''
            description = _(
                "Pipedrive custom field '%(field)s' created successfully for %(entity)s."
            ) % {'field': field_name, 'entity': entity_label}
            if field_key:
                description += ' ' + _('Field key: %s') % field_key
            self.env['opd_integration.pipedrivelogger'].create_logger(
                '', status_code, record_direction, module_name, description,
                request_payload, response_payload or description, operation,
                'resolve', 'success', operation_type, field_name
            )
        elif log_type == 'warning':
            description = field_data if isinstance(field_data, str) else _(
                "Pipedrive custom field '%(field)s' must be created manually for %(entity)s."
            ) % {'field': field_name, 'entity': entity_label}
            self.env['opd_integration.pipedrivelogger'].create_logger(
                '', '', record_direction, module_name, description,
                request_payload, response_payload, operation,
                'pending', 'warning', operation_type, field_name
            )
        else:
            description = _(
                "Failed to create Pipedrive custom field '%(field)s' for %(entity)s."
            ) % {'field': field_name, 'entity': entity_label}
            self.env['opd_integration.pipedrivelogger'].create_logger(
                status_code, status_code, record_direction, module_name, description,
                request_payload, response_payload, operation,
                'pending', 'error', operation_type, field_name
            )

    @api.model
    def ensure_pipedrive_required_custom_fields(self, instance_id, entity_key, operation_type='manually',
                                              refresh_fields=True):
        """
        Ensure sync_to_odoo and odoo_id custom fields exist in Pipedrive for the given entity.
        Creates missing fields via the Pipedrive v1 Fields API and optionally refreshes Odoo field mappers.
        """
        config = PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG.get(entity_key)
        if not config:
            return {'created': [], 'skipped': [], 'errors': [_('Unknown entity: %s') % entity_key]}

        api_token = instance_id.api_token
        if not api_token:
            return {'created': [], 'skipped': [], 'errors': [_('API token is missing.')]}

        existing_fields, response = self._fetch_pipedrive_custom_fields(api_token, config['endpoint'])
        if existing_fields is None:
            error_details = f"{response.status_code} - {response.reason}"
            description = _("Failed to fetch %(entity)s fields from Pipedrive") % {
                'entity': config['display_name'],
            }
            self.http_log_error(
                error_details, config['logger_name'], description, {}, response.text,
                'pipedrive', operation_type, '', f"HTTP {response.status_code}"
            )
            return {
                'created': [],
                'skipped': [],
                'manual_required': [],
                'errors': [
                    _("Failed to fetch %(entity)s fields from Pipedrive.") % {
                        'entity': config['display_name'],
                    }
                ],
            }

        result = {'created': [], 'skipped': [], 'manual_required': [], 'errors': []}
        logger_name = config['logger_name']
        supports_field_creation = config.get('supports_field_creation', True)

        for field_def in REQUIRED_PIPEDRIVE_SYNC_FIELDS:
            field_name = field_def['name']
            label = f"{config['display_name']}: {field_name}"
            if self._pipedrive_custom_field_exists(existing_fields, field_name):
                result['skipped'].append(label)
                continue

            if not supports_field_creation:
                manual_message = _(
                    "Pipedrive does not provide an API to create Lead custom fields. "
                    "Please create the '%(field)s' field manually in Pipedrive under "
                    "Settings > Data fields > Leads, then click Import Lead Fields."
                ) % {'field': field_name}
                result['manual_required'].append(label)
                self.log_custom_field_operation(
                    logger_name, field_name, operation_type,
                    field_data=manual_message, log_type='warning'
                )
                continue

            status, _field_data = self._create_pipedrive_custom_field(
                api_token, config['endpoint'], field_def, logger_name, operation_type
            )
            if status == 'created':
                result['created'].append(label)
                instance_id.env.cr.commit()
                existing_fields, _response = self._fetch_pipedrive_custom_fields(api_token, config['endpoint'])
                if existing_fields is None:
                    existing_fields = []
            else:
                result['errors'].append(label)

        if refresh_fields and (result['created'] or result['skipped']):
            mapper_model = self.env[config['mapper_model']]
            getattr(mapper_model, config['fetch_fields_method'])()

        return result

    @api.model
    def ensure_all_pipedrive_required_custom_fields(self, instance_id, operation_type='manually', refresh_fields=True):
        """Ensure required custom fields exist for all sync-enabled Pipedrive entities."""
        combined = {'created': [], 'skipped': [], 'manual_required': [], 'errors': []}
        for entity_key in PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG:
            entity_result = self.ensure_pipedrive_required_custom_fields(
                instance_id, entity_key, operation_type=operation_type, refresh_fields=refresh_fields
            )
            for key in combined:
                combined[key].extend(entity_result.get(key, []))
        return combined

    @api.model
    def _format_custom_fields_notification(self, result):
        parts = []
        if result.get('created'):
            parts.append(_("Created: %s") % ', '.join(result['created']))
        if result.get('skipped'):
            parts.append(_("Already exist: %s") % ', '.join(result['skipped']))
        if result.get('manual_required'):
            parts.append(
                _("Manual setup required (Lead fields): %s") % ', '.join(result['manual_required'])
            )
        if result.get('errors'):
            parts.append(_("Errors: %s") % ', '.join(result['errors']))
        return '\n'.join(parts) if parts else _('All required Pipedrive custom fields are already configured.')

    @api.model
    def custom_fields_notification_action(self, result, title):
        message = self._format_custom_fields_notification(result)
        notif_type = 'success'
        if result.get('errors'):
            notif_type = 'warning' if result.get('created') or result.get('skipped') else 'danger'
        elif result.get('manual_required'):
            notif_type = 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notif_type,
                'sticky': bool(result.get('errors') or result.get('manual_required')),
            },
        }

    # ------------------------------------- Create Odoo Activity ------------------------------- #
    def create_odoo_activities(self, instance_id, activity, odoo_record, odoo_model_name, activity_type_mapping,
                               logger_name, operation_type):
        """
        Create activities in Odoo based on the activity type.

        Args:
            instance_id: The Pipedrive instance ID.
            activity: The activity data from Pipedrive.
            odoo_record: The Odoo record to which the activity is related.
            odoo_model_name: The name of the Odoo model.
            activity_type_mapping: A dictionary mapping activity types to their corresponding Odoo activity type IDs and instance field names.

        Returns:
            None
        """
        activity_type = activity.get('type')

        if activity_type in activity_type_mapping:
            activity_type_id, instance_field = activity_type_mapping[activity_type]
            if getattr(instance_id, instance_field):
                self.create_activity(activity, odoo_record, odoo_model_name, logger_name, operation_type,
                                     activity_type_id=activity_type_id)

    # -------- Fetches activities and notes from pipedrive and creates them in odoo ----------- #
    def fetch_and_process_activities_and_notes(self, instance_id, pipedrive_record_id, pipedrive_model_name, odoo_record, odoo_model_name,
         calls_field,tasks_field,emails_field, meetings_field, notes_field, activities_endpoint_base,
         notes_endpoint_base, files_endpoint_base, email_endpoint_base, api_token, logger_name, operation_type, check_hash=True):
        """
        Fetches activities and notes from Pipedrive and creates them in Odoo.

        Args:
            instance_id: Pipedrive instance ID.
            odoo_record: Record in Odoo.
            Odoo_model_name (str): Name of the Odoo model.
            Calls_field (str): Field indicating whether to create call activities.
            Tasks_field (str): Field indicating whether to create task activities.
            Emails_field (str): Field indicating whether to create email activities.
            Meetings_field (str): Field indicating whether to create meeting activities.
            Notes_field (str): Field indicating whether to create notes.
            Activities_endpoint (str): Endpoint to fetch activities.
            Notes_endpoint (str): Endpoint to fetch notes.
            Api_token (str): Pipedrive API token.

        Returns:
            None
        """
        try:
            activity_payload = {}
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            # Get last sync date
            last_sync_date = datetime.now()
            if pipedrive_model_name == 'organizations':
                last_sync_date = getattr(instance_id, 'pipedrive_company_last_sync_date')
            elif pipedrive_model_name == 'persons':
                last_sync_date = getattr(instance_id, 'pipedrive_contact_last_sync_date')
            elif pipedrive_model_name == 'leads':
                last_sync_date = getattr(instance_id, 'pipedrive_lead_last_sync_date')
            elif pipedrive_model_name == 'deals':
                last_sync_date = getattr(instance_id, 'pipedrive_deal_last_sync_date')

            activities = []
            limit = instance_id.pagination_size
            if limit <= 0:
                raise UserError(_('Pagination size should be greater than zero.'))

            cursor = None  # v2 uses cursor instead of start
            base_endpoint = f"{activities_endpoint_base}&limit={limit}"

            while True:
                # Build endpoint dynamically
                endpoint = f"{base_endpoint}&cursor={cursor}" if cursor else base_endpoint

                activities_response = self.env['opd.mapper.mixin'].fetch_data(
                    endpoint, headers, activity_payload, method="GET"
                )

                if activities_response.status_code == 200:
                    response_json = activities_response.json()
                    activities = response_json.get('data', [])
                    additional_data = response_json.get('additional_data', {})
                    cursor = additional_data.get('next_cursor')  # <-- use cursor for next page

                    if not activities:
                        break

                    # Define activity mapping
                    activity_type_mapping = {
                        'call': (2, calls_field),
                        'email': (1, emails_field),
                        'meeting': (3, meetings_field),
                        'task': (4, tasks_field)
                    }

                    # Process activities
                    for activity in activities:
                        update_time = activity.get('update_time')
                        # Handle v2 timestamp (RFC3339)
                        try:
                            activity_update_time = datetime.strptime(update_time, "%Y-%m-%dT%H:%M:%SZ")
                        except Exception:
                            activity_update_time = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")

                        if not last_sync_date or activity_update_time > last_sync_date:
                            self.create_odoo_activities(
                                instance_id, activity, odoo_record, odoo_model_name,
                                activity_type_mapping, logger_name, operation_type
                            )

                    # If no next cursor, break the loop
                    if not cursor:
                        break

            # ------------------------------ process pipedrive notes --------------------- #

            # Check if notes field exists for this instance
            notes_attr = getattr(instance_id, notes_field, None)
            notes = []
            start = 0
            while True:
                if notes_attr:
                    # Fetch notes from Pipedrive
                    notes_endpoint = f"{notes_endpoint_base}&start={start}&limit={limit}"
                    notes_response = self.env['opd.mapper.mixin'].fetch_data(notes_endpoint, headers, activity_payload,
                                                                             method="GET")

                    # Check the notes response
                    if notes_response.status_code == 200:
                        notes_response_json = notes_response.json()
                        notes = notes_response_json.get('data', [])
                        if not notes:
                            break
                    else:
                        self.http_log_error(
                            f"Failed to fetch {logger_name} associated notes: {notes_response.text}",
                            "note",f"Error fetching {logger_name} associated notes from Pipedrive",
                            activity_payload,notes_response.text,'odoo',operation_type,'',
                            f"HTTP {notes_response.status_code}")

                    # Process notes only if notes_attr is set and notes are fetched
                    if notes:
                        for note in notes:
                            update_time = note.get('update_time')
                            try:
                                note_update_time = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                            except (TypeError, ValueError):
                                continue

                            if not last_sync_date or note_update_time > last_sync_date or not check_hash:
                                note_pipedrive_id = note.get('id')
                                self.create_pipedrive_to_odoo_note(
                                    note, note_pipedrive_id, odoo_record, odoo_model_name,
                                    logger_name, operation_type)

                if len(notes) < limit:
                    break

                start += limit

            # Pipedrive to Odoo Files and Mail messages
            if logger_name != 'lead':
                self.sync_pipedrive_to_odoo_files(instance_id, logger_name, files_endpoint_base, headers, activity_payload,
                                             odoo_record, odoo_model_name, api_token, operation_type)

                self.sync_pipedrive_to_odoo_mail_messages(instance_id, logger_name, email_endpoint_base, headers, activity_payload, odoo_record, odoo_model_name, emails_field, api_token, operation_type)

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} associated activities Create/Update in the Odoo.'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)

    # ------------------------ Sync Pipedrive to Odoo Files -------------------- #

    def sync_pipedrive_to_odoo_files(self, instance_id, logger_name, files_endpoint_base, headers, activity_payload, odoo_record, odoo_model_name, api_token, operation_type):
        # Determine the dynamic field for file sync
        start = 0
        limit = instance_id.pagination_size
        files = []

        while True:
            file_field_map = {
                'company': 'is_company_files',
                'contact': 'is_contact_files',
                'deal': 'is_deal_files'
            }

            # Get the field name from logger_name
            files_field = file_field_map.get(logger_name)
            files_attr = getattr(instance_id, files_field, None)
            if files_endpoint_base and files_attr:
                # Fetch files from Pipedrive
                files_endpoint = f"{files_endpoint_base}&start={start}&limit={limit}"

                files_response = self.env['opd.mapper.mixin'].fetch_data(files_endpoint, headers, activity_payload,
                                                                         method="GET")
                # Check the file response
                if files_response.status_code == 200:
                    files_response_json = files_response.json()
                    files = files_response_json.get('data', [])
                    if not files:
                        break
                else:
                    self.http_log_error(
                        f"Failed to fetch {logger_name} associated files: {files_response.text}",
                        "activity",
                        f"Error fetching {logger_name} associated files from Pipedrive",
                        activity_payload, files_response.text, 'odoo', operation_type, '',
                        f"HTTP {files_response.status_code}")

                if files:
                    for file in files:
                        file_url = f"{file['url']}?api_token={api_token}"
                        file_name = file.get("name", file.get("file_name", "unnamed.pdf"))
                        file_type = file.get("file_type", "pdf")
                        file_id = file.get("id")

                        # Download the file from Pipedrive
                        file_response = requests.get(file_url)
                        if file_response.status_code != 200:
                            continue

                        # Encode file content to base64
                        encoded_file = base64.b64encode(file_response.content)

                        # Prevent duplicate uploads
                        existing = self.env['ir.attachment'].search([
                            ('res_model', '=', odoo_model_name),
                            ('res_id', '=', odoo_record.id),
                            ('name', '=', file_name)
                        ], limit=1)
                        if existing:
                            continue
                        else:
                            # Create attachment in Odoo
                            odoo_file_create_vals = {
                                'name': file_name,
                                'type': 'binary',
                                'datas': encoded_file,
                                'res_model': odoo_model_name,
                                'res_id': odoo_record.id,
                                'mimetype': f'application/{file_type}',
                            }
                            file_record = self.env['ir.attachment'].create(odoo_file_create_vals)
                            file_record.env.cr.commit()
                            odoo_record.message_post(
                                body=f"File synced from Pipedrive: {file_name}",
                                attachment_ids=[file_record.id]
                            )
                            self.activity_log_operation(logger_name, file_id, odoo_file_create_vals, 'create', 'file',
                                                        'odoo', operation_type)
            if len(files) < limit:
                break

            start += limit

    # Get Full Email Body
    def get_full_email_body(self, mail_id, api_token):
        """
        Fetch full email content using Pipedrive Mail Message ID.
        """
        detail_url = f'{self.__API_BASE_URL}/mailbox/mailMessages/{mail_id}?api_token={api_token}'
        response = requests.get(detail_url)
        if response.status_code == 200:
            data = response.json().get('data', {})
            body_url = data.get('body_url')
            if body_url:
                body_response = requests.get(body_url)
                if body_response.status_code == 200:
                    return body_response.text
        return ''

    # ------------------------ Sync Pipedrive to Odoo Mail Messages -------------------- #
    def sync_pipedrive_to_odoo_mail_messages(self, instance_id, logger_name, email_endpoint_base, headers, activity_payload, odoo_record, odoo_model_name, emails_field, api_token, operation_type):
        emails_attr = getattr(instance_id, emails_field, None)
        emails = []

        start = 0
        limit = instance_id.pagination_size

        while True:
            if email_endpoint_base and emails_attr:
                # Fetch files from Pipedrive
                email_endpoint = f"{email_endpoint_base}&start={start}&limit={limit}"
                emails_response = self.env['opd.mapper.mixin'].fetch_data(email_endpoint, headers, activity_payload,
                                                                          method="GET")
                # Check the emails response
                if emails_response.status_code == 200:
                    emails_response_json = emails_response.json()
                    emails = emails_response_json.get('data', [])
                    if not emails:
                        break
                else:
                    self.http_log_error(
                        f"Failed to fetch {logger_name} associated mailMassages: {emails_response.text}",
                        "activity",
                        f"Error fetching {logger_name} associated mailMassages from Pipedrive",
                        activity_payload, emails_response.text, 'odoo', operation_type, '',
                        f"HTTP {emails_response.status_code}")
                if emails:
                    for email in emails:
                        data = email.get('data', {})
                        external_id = data.get('id')
                        subject = data.get('subject', 'No Subject')
                        body_text = data.get('snippet', '')
                        timestamp = data.get('timestamp')  # ISO 8601 format
                        converted_date = datetime.strptime(timestamp.replace('Z', ''), '%Y-%m-%dT%H:%M:%S.%f')
                        formatted_date = converted_date.strftime('%Y-%m-%d %H:%M:%S')
                        sender = data.get('from', [{}])[0].get('email_address')
                        receiver = data.get('to', [{}])[0].get('email_address')

                        existing_email_message = self.env['mail.message'].search([
                            ('pipedrive_email_id', '=', external_id), ('res_id', '=', odoo_record.id), ('model', '=', odoo_model_name)
                        ], limit=1)

                        # Fetch the full body from mailMessages/<id>
                        full_body = self.get_full_email_body(external_id, api_token)


                        if existing_email_message:
                            message_vals = {
                                'subject': subject,
                                'body': full_body or body_text,  # fallback to snippet,
                                'email_from': sender,
                                'reply_to': receiver,
                                'model': odoo_model_name,
                                'res_id': odoo_record.id,
                                'message_type': 'email',
                                'subtype_id': self.env.ref('mail.mt_note').id,
                                'pipedrive_email_id': external_id,  # Custom tracking field
                                'date': formatted_date,
                            }
                            existing_email_message.write(message_vals)
                            existing_email_message.env.cr.commit()
                            self.activity_log_operation(logger_name, external_id, message_vals, 'write', 'mailmessage',
                                                        'odoo', operation_type)

                        else:
                            # Create mail.message
                            message_vals = {
                                'subject': subject,
                                'body':  full_body or data.get('snippet', ''),  # fallback to snippet,
                                'email_from': sender,
                                'reply_to': receiver,
                                'model': odoo_model_name,
                                'res_id': odoo_record.id,
                                'message_type': 'email',
                                'subtype_id': self.env.ref('mail.mt_note').id,
                                'pipedrive_email_id': external_id,  # Custom tracking field
                                'date': formatted_date,
                            }
                            message = self.env['mail.message'].sudo().create(message_vals)
                            message.env.cr.commit()
                            self.activity_log_operation(logger_name, external_id, message_vals, 'create', 'mailmessage',
                                                        'odoo', operation_type)

                        # Handle attachments
                        for att in data.get('attachments', []):
                            file_url = att.get('url')
                            pipedrive_attachment_id = att.get('id')
                            file_name = att.get('name')
                            file_type = att.get("file_type", "pdf")
                            if file_url:
                                # Download the attachment content
                                email_file_url = f"{file_url}?api_token={api_token}"
                                att_response = requests.get(email_file_url)
                                if att_response.status_code == 200:
                                    # Prevent duplicate uploads
                                    existing = self.env['ir.attachment'].search([
                                        ('res_model', '=', odoo_model_name),
                                        ('res_id', '=', odoo_record.id),
                                        ('pipedrive_attachment_id', '=', pipedrive_attachment_id)
                                    ], limit=1)
                                    if existing:
                                        continue
                                    else:
                                        odoo_email_record = self.env['ir.attachment'].sudo().create({
                                            'name': file_name,
                                            'type': 'binary',
                                            'datas': base64.b64encode(att_response.content),
                                            'res_model': odoo_model_name,
                                            'res_id': odoo_record.id,
                                            'mimetype': f'application/{file_type}',
                                            'pipedrive_attachment_id': pipedrive_attachment_id
                                        })
                                        odoo_email_record.env.cr.commit()
                                        odoo_record.message_post(
                                            body=f"File synced from Pipedrive: {file_name}",
                                            attachment_ids=[odoo_email_record.id]
                                        )
            if len(emails) < limit:
                break

            start += limit

    # --------------------------- Fetch Activity For Organization, Contacts, Deals ----------------------------------#
    def fetch_activity(self, instance_id, odoo_record, odoo_model_name, calls_field, tasks_field, emails_field,
                       meetings_field, notes_field, pipedrive_model_name, record_id, api_token, logger_name, operation_type,
                       check_hash=True):
        """
        Description:
            Fetches activities and notes for a record from Pipedrive and creates them in Odoo.

        Args:
            instance_id: Pipedrive instance ID.
            odoo_record: Record in Odoo.
            Calls_field (str): Field indicating whether to create call activities.
            Tasks_field (str): Field indicating whether to create task activities.
            Emails_field (str): Field indicating whether to create email activities.
            Meetings_field (str): Field indicating whether to create meeting activities.
            Notes_field (str): Field indicating whether to create notes.
            Pipedrive_model_name (str): Name of the Pipedrive model.
            Record_id (int): ID of the record in Pipedrive.
            Api_token (str): Pipedrive API token.

        Returns:
            None
        """
        # Map logger_name → related_field
        related_field = {
            'company': 'org_id',
            'contact': 'person_id',
            'deal': 'deal_id'
        }.get(logger_name)

        if not related_field:
            raise ValueError(f"Invalid logger_name: {logger_name}")

        activities_endpoint = f"{instance_id.api_base_url}/activities?{related_field}={record_id}&api_token={api_token}"
        notes_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}/{record_id}/notes?api_token={api_token}"
        files_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}/{record_id}/files?api_token={api_token}"
        email_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}/{record_id}/mailMessages?api_token={api_token}"
        self.fetch_and_process_activities_and_notes(instance_id, record_id, pipedrive_model_name, odoo_record, odoo_model_name,
             calls_field, tasks_field,emails_field, meetings_field, notes_field, activities_endpoint,
             notes_endpoint, files_endpoint, email_endpoint, api_token, logger_name, operation_type, check_hash)

    # --------------------------- Fetch Activity For Leads ----------------------------------#
    def fetch_activity_for_leads(self, instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
                                 emails_field, meetings_field, notes_field, api_token, contact_model, record_id,
                                 type, object, logger_name, operation_type, check_hash=True):
        """
        Description:
            Fetches activities and notes for a lead record from Pipedrive and creates them in Odoo.

        Args:
            instance_id (opd.pipedriveinstance): Pipedrive instance ID.
            Odoo_record (odoo.models.Model): Record in Odoo.
            Odoo_model_name (str): Name of the Odoo model.
            Calls_field (str): Field indicating whether to create call activities.
            Tasks_field (str): Field indicating whether to create task activities.
            Emails_field (str): Field indicating whether to create email activities.
            Meetings_field (str): Field indicating whether to create meeting activities.
            Notes_field (str): Field indicating whether to create notes.
            Api_token (str): Pipedrive API token.
            Contact_model (str): Name of the Pipedrive contact model.
            Record_id (int): ID of the record in Pipedrive.
            Field_id (int): ID of the field to use for filtering activities.
            Type (str): Type of the filter (e.g., "activities").
            Object (str): Type of the object (e.g., "activity").

        Returns:
            None
        """
        activity_field_id = self.get_update_time_field('opd.activitymapper', 'lead_id')
        lead_activity_id = self.fetch_activity_filter_id(api_token, record_id, activity_field_id, type, object,
                                                         logger_name, '=', operation_type)
        activities_endpoint = f"{self.__API_BASE_URL}{contact_model}?filter_id={lead_activity_id}&api_token={api_token}"
        notes_endpoint = f"{self.__API_BASE_URL}notes?lead_id={record_id}&api_token={api_token}"
        pipedrive_model_name = 'leads'
        self.fetch_and_process_activities_and_notes(instance_id, record_id, pipedrive_model_name, odoo_record, odoo_model_name,
        calls_field, tasks_field,emails_field, meetings_field, notes_field, activities_endpoint,
        notes_endpoint, '', '', api_token, logger_name, operation_type, check_hash)

    # ------------------------- Create Activity Function ------------------------ #

    def create_activity(self, activity, odoo_record, odoo_model_name, logger_name, operation_type, activity_type_id):
        """
        Creates an activity for the company.

        Args:
            activity (dict): Details of the activity to be created.
            odoo_record: Record in Odoo.
            odoo_model_name (str): Name of the Odoo model.
            activity_type_id (int): ID of the activity type.

        Returns:
            None
        """
        try:
            # Ensure activity is a dictionary
            if not isinstance(activity, dict):
                return

            note = activity.get('note') if activity.get('note') else None
            if activity.get('note'):
                # Parse the HTML string using BeautifulSoup
                note_str = BeautifulSoup(note, 'html.parser')
                # Extract the text content from the HTML using the get_text() method
                note_text = note_str.get_text()
            else:
                note_text = ''

            # Check if the activity already exists
            existing_activity = self.env['mail.activity'].search([
                ('pipedrive_activity_id', '=', activity.get('id')), ('res_id', '=', odoo_record.id), ('res_model', '=', odoo_model_name)], limit=1)
            activity_user_id = activity.get('user_id')
            user_record = self.env['res.users'].search(
                [('pipedrive_id', '=', activity_user_id), ('share', '=', False), ('active', '=', True)], limit=1)
            if user_record:
                user_id = user_record.id
            else:
                user_id = self.env.user.id
            activity_name = activity.get('type')  # Assuming 'type' contains the activity name like 'call', 'meeting', etc.
            active = not activity.get('done', False)

            update_vals = {
                'date_deadline': activity.get('due_date'),
                'summary': activity.get('subject'),
                'note': note_text,
                'user_id': user_id
            }
            if existing_activity:
                if activity_user_id == activity_user_id:
                    update_vals.pop('user_id', None)
                else:
                    update_vals = update_vals
                existing_activity.write(update_vals)
                if not active:  # ← You can control this with a condition or sync flag
                    existing_activity.action_done()
                else:
                    existing_activity.env.cr.commit()
                self.activity_log_operation(logger_name, activity.get('id'), update_vals, 'update', activity_name,
                                            'odoo', operation_type)
            else:
                res_model_id = self.env['ir.model']._get(odoo_model_name).id

                if not odoo_record.id:
                    return

                vals = {
                    'activity_type_id': activity_type_id,
                    'pipedrive_activity_id': activity.get('id'),
                    'res_id': odoo_record.id,
                    'user_id': user_id,
                    'date_deadline': activity.get('due_date'),
                    'res_model_id': res_model_id,
                    'summary': activity.get('subject'),
                    'note': note_text,
                }
                new_activity = self.env['mail.activity'].create(vals)
                if not active:  # ← You can control this with a condition or sync flag
                    new_activity.action_done()
                else:
                    new_activity.env.cr.commit()
                self.activity_log_operation(logger_name, activity.get('id'), vals, 'create', activity_name, 'odoo', operation_type)

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create/update activity'
            self.exception_log_error(error_details, 'activity', description, 'odoo', operation_type, '', error_type)

    # ------------------------- Create Pipedrive to Odoo Note Function ------------------------ #
    def create_pipedrive_to_odoo_note(self, note, note_pipedrive_id, odoo_record, odoo_model_name, logger_name, operation_type):
        """
            Description:
                Creates a note.

            Args:
                note (dict): Details of the note to be created.
                odoo_record: Record in Odoo.
                odoo_model_name (str): Name of the Odoo model.
            Returns:
                None    """
        try:
            odoo_record_id = self.get_record_id(odoo_record)
            existing_note = self.env['mail.message'].search([
                ('pipedrive_notes_id', '=', note_pipedrive_id), ('res_id', '=', odoo_record_id)], limit=1)

            if existing_note:
                update_vals = {
                    'body': note.get('content'),
                }
                existing_note.write(update_vals)
                existing_note.env.cr.commit()
                self.activity_log_operation(logger_name, note_pipedrive_id, update_vals, 'update', 'note', 'odoo', operation_type)

            else:
                vals = {
                    'res_id': odoo_record_id,
                    'body': note.get('content'),
                    'pipedrive_notes_id': note_pipedrive_id,
                    'message_type': 'comment',
                    'model': odoo_model_name
                }
                new_note = self.env['mail.message'].create(vals)
                new_note.env.cr.commit()
                self.activity_log_operation(logger_name, note_pipedrive_id, vals, 'create', 'note', 'odoo', operation_type)
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create/update note'
            self.exception_log_error(error_details, 'note', description, 'odoo', operation_type, note_pipedrive_id, error_type)

    # --------------------------------- Fetch Common Filter ID ------------------------------------- #

    def fetch_filter_id_common(self, api_token, value, sync_value, field_id, sync_field_id, type, object, name,
                               operator, logger_name, last_field_id, last_field_value, operation_type):
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
                "name": name,
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
                                    "operator": operator,
                                    "value": value,
                                    "extra_value": None
                                },
                                {
                                    "object": object,
                                    "field_id": sync_field_id,
                                    "operator": "=",
                                    "value": sync_value,
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
            response = self.fetch_data(url, headers, payload, method="POST")

            if response.status_code in [200, 201]:
                response_json = response.json()
                filter_id = response_json.get('data', {}).get('id')
                # ✅ Store filter ID in Odoo
                if filter_id:
                    self.env['opd.filter'].create({'filter_id': str(filter_id)})

                return filter_id
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive {logger_name} filter ID"
                self.http_log_error(error_details, logger_name, description, payload, response.text,
                                    'odoo', operation_type, '', f"HTTP {response.status_code}")
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create {logger_name} filter ID'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)
            return None

        # ------------------------------ Fetch Common Crm Filter ID -------------------------------- #

    def fetch_common_filter_id(self, api_token, value, sync_value, field_id, sync_field_id, type, object, name,
                               operator, logger_name, operation_type):
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
                "name": name,
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
                                    "operator": operator,
                                    "value": value,
                                    "extra_value": None
                                },
                                {
                                    "object": object,
                                    "field_id": sync_field_id,
                                    "operator": "=",
                                    "value": sync_value,
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
            response = self.fetch_data(url, headers, payload, method="POST")

            if response.status_code in [200, 201]:
                response_json = response.json()
                filter_id = response_json.get('data', {}).get('id')
                if filter_id:
                    self.env['opd.filter'].create({'filter_id': str(filter_id)})
                return filter_id
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive {logger_name} filter ID"
                self.http_log_error(error_details, logger_name, description, payload, response.text,
                                    'odoo', operation_type, '', f"HTTP {response.status_code}")
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create {logger_name} filter ID'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)
            return None

    # ------------------- Create Filter ID To Fetch the Activity Of Pipedrive ----------- #
    def fetch_activity_filter_id(self, api_token, value, field_id, type, object, logger_name, operator, operation_type):
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
                "name": 'activity',
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
                                    "operator": operator,
                                    "value": value,
                                    "extra_value": None
                                },
                            ]
                        },
                        {
                            "glue": "or",
                            "conditions": []
                        }
                    ]
                },
            })
            response = self.fetch_data(url, headers, payload, method="POST")
            if response.status_code in [200, 201]:
                response_json = response.json()
                filter_id = response_json.get('data', {}).get('id')
                if filter_id:
                    self.env['opd.filter'].create({'filter_id': str(filter_id)})
                return filter_id
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive {logger_name} filter ID"
                self.http_log_error(error_details, logger_name, description, payload, response.text,
                                    'odoo', operation_type, '', f"HTTP {response.status_code}")
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while create {logger_name} filter ID'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)
            return None

    # --------------------------- Fetch Filter ID For Organization Related Leads ------------------------ #

    def fetch_filter_id(self, api_token, last_sync_date, sync_value, field_id, sync_field_id, type, object,
                        logger_name, last_field_id, last_field_value, operation_type):
        """
        Description:
            Fetches the filter ID from Pipedrive based on certain conditions.

        Args:
            api_token (str): Pipedrive API token.
            last_sync_date (Datetime): Last synchronization date.
            sync_value (str): Sync value to filter records.
            field_id (int): ID of the field.
            sync_field_id (int): ID of the sync field.
            type (str): Type of the filter (e.g., "org").
            object (str): Type of the object (e.g., "Organization").
            logger_name (str): Name of the logger for logging purposes.

        Returns:
            str: Filter ID retrieved from Pipedrive.
        """
        name = "Filter Leads by Update Time"
        operator = ">="
        value = last_sync_date
        is_sync = sync_value
        sync_field_id = sync_field_id
        return self.fetch_filter_id_common(api_token, value, is_sync, field_id, sync_field_id, type, object, name,
                                           operator, logger_name, last_field_id, last_field_value, operation_type)

    # ---------------------------- Fetch Filter ID For Related Data ----------------------- #

    def fetch_related_filter_id(self, api_token, last_sync_date, sync_value, field_id, sync_field_id, type, object,
                                logger_name, operation_type):
        """
        Description:
            Fetches the filter ID from Pipedrive based on certain conditions.

        Args:
            api_token (str): Pipedrive API token.
            last_sync_date (Datetime): Last synchronization date.
            sync_value (str): Sync value to filter records.
            field_id (int): ID of the field.
            sync_field_id (int): ID of the sync field.
            type (str): Type of the filter (e.g., "org").
            object (str): Type of the object (e.g., "Organization").
            logger_name (str): Name of the logger for logging purposes.

        Returns:
            str: Filter ID retrieved from Pipedrive.
        """
        name = "Filter Leads by Update Time"
        operator = ">="
        value = last_sync_date
        is_sync = sync_value
        sync_field_id = sync_field_id
        return self.fetch_common_filter_id(api_token, value, is_sync, field_id, sync_field_id, type, object, name,
                                           operator, logger_name, operation_type)

    # ---------------------------------- Fetch Filter ID For CRM Related Leads ------------------------- #
    def fetch_crm_filter_id(self, api_token, organization_id, sync_value, field_id, sync_field_id, type, object,
                            logger_name, operation_type):
        """
        Description:
            Fetches the filter ID from Pipedrive based on certain conditions.

        Args:
            api_token (str): Pipedrive API token.
            organization_id (int): ID of the organization.
            sync_value (str): Sync value to filter records.
            field_id (int): ID of the field.
            sync_field_id (int): ID of the sync field.
            type (str): Type of the filter (e.g., "deals").
            object (str): Type of the object (e.g., "deal").
            logger_name (str): Name of the logger for logging purposes.

        Returns:
            str: Filter ID retrieved from Pipedrive.
        """
        name = "Filter Organizations by Update Time"
        operator = "="
        value = organization_id
        is_sync = sync_value
        sync_field_id = sync_field_id
        return self.fetch_common_filter_id(api_token, value, is_sync, field_id, sync_field_id, type, object, name,
                                           operator, logger_name, operation_type)

    # ------------------------ Get Module Name And Direction -------------------- #
    def get_module_and_direction(self, logger_name, model_name):
        """
        Determines the module name and record direction based on the logger and model names.

        Args:
            logger_name (str): The name of the logger (e.g., 'contact', 'account').
            model_name (str): The model name in Odoo or Pipedrive.

        Returns:
            tuple: A tuple containing (module_name, record_direction).
        """
        module_mapping = {
            'contact': 'contacts',
            'company': 'companies',
            'lead': 'leads',
            'deal': 'deals',
            'product': 'products',
            'user': 'users',
            'activity': 'activities',
            'note': 'notes',
            'association': 'associations',
            'file': 'files',
            'mailmessage': 'mailmessages',
            'lead_label': 'leadLabels'
        }

        if model_name == 'odoo':
            record_direction = 'pto'
        elif model_name == 'pipedrive':
            record_direction = 'otp'
        else:
            record_direction = ''

        module_name = module_mapping.get(logger_name.lower(), '')

        return module_name, record_direction

    # ----------------------------------- Method For Log Operation Created And Updated ------------------------- #

    def log_operation(self, logger_name, status_code, record_id, record_data, operation_type, model_name, record_operation,
                      parent_name=None,parent_id=None):
        """
        Logs the operation performed on a record in Odoo.

        Args:
             logger_name (str): The name of the logger (e.g., 'contact', 'company').
            record_id (int): The ID of the record in Pipedrive.
            record_data (dict): The data of the record being created or updated.
            operation_type (str): The type of operation performed ('create' or 'update').
            model_name (str): The name of the model in Odoo where the record is being created or updated.
            parent_name (str, optional): The name of the parent record, if any. Defaults to None.
            parent_id (int, optional): The ID of the parent record, if any. Defaults to None.

        Returns:
            None
        """

        logger_name_capitalize = logger_name.capitalize()
        if parent_name == None and parent_id == None:
            if operation_type == 'create':
                operation = f'Create {logger_name}'
                description = f'{logger_name_capitalize} created successfully in {model_name}. {logger_name_capitalize} ID: {record_id}'
                response_payload = f'{logger_name_capitalize} created successfully'
            else:
                operation = f'Update {logger_name}'
                description = f'{logger_name_capitalize} updated successfully in {model_name}. {logger_name_capitalize} ID: {record_id}'
                response_payload = f'{logger_name_capitalize} updated successfully'
        else:
            if operation_type == 'create':
                operation = f'Create {logger_name}'
                description = f'{parent_name.capitalize()} related {logger_name} created successfully in {model_name}. {logger_name_capitalize} ID: {record_id}, {parent_name.capitalize()} ID: {parent_id}'
                response_payload = f'{logger_name_capitalize} created successfully'
            else:
                operation = f'Update {logger_name}'
                description = f'{parent_name.capitalize()} related {logger_name} updated successfully in {model_name}. {logger_name_capitalize} ID: {record_id}, {parent_name.capitalize()} ID: {parent_id}'
                response_payload = f'{logger_name_capitalize} updated Successfully'

        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)

        self.env['opd_integration.pipedrivelogger'].create_logger(
            '', status_code, record_direction, module_name, description, record_data,
            response_payload, operation, 'resolve', 'success', record_operation, record_id
        )

    # ----------------------------------- Method For Log Operation Warning Message ------------------------- #

    def log_operation_warning(self, logger_name, description, operation, model_name, payload, operation_type, record_id):
        """
        Logs the operation performed on a record in Odoo.

        Args:
             logger_name (str): The name of the logger (e.g., 'contact', 'company').
            record_id (int): The ID of the record in Pipedrive.
            record_data (dict): The data of the record being created or updated.
            operation_type (str): The type of operation performed ('create' or 'update').
            model_name (str): The name of the model in Odoo where the record is being created or updated.
            parent_name (str, optional): The name of the parent record, if any. Defaults to None.
            parent_id (int, optional): The ID of the parent record, if any. Defaults to None.

        Returns:
            None
        """

        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)

        self.env['opd_integration.pipedrivelogger'].create_logger(
            '', '', record_direction, module_name, description, '',
            payload, operation, 'pending', 'warning', operation_type, record_id
        )

    # ------------- Logs the operation performed on a record in Odoo --------------- #
    def activity_log_operation(self, logger_name, record_id, record_data, operation_type, activity_name, model_name, record_operation):
        """
        Logs the operation performed on a record in Odoo.

        Args:
            logger_name (str): The name of the logger (e.g., 'contact', 'company').
            record_id (int): The ID of the record in Pipedrive.
            record_data (dict): The data of the record being created or updated.
            operation_type (str): The type of operation performed ('create' or 'update').

        Returns:
            None
        """
        logger_name_capitalize = logger_name.capitalize()
        if operation_type == 'create':
            operation = f'Create {logger_name} associated {activity_name}'
            description = f'{logger_name_capitalize} associated {activity_name} created successfully in Odoo. {activity_name.capitalize()} ID: {record_id}'
            response_payload = f'{activity_name.capitalize()} created successfully'
        else:
            operation = f'Update {logger_name} associated {activity_name}'
            description = f'{logger_name_capitalize} associated {activity_name} updated successfully in Odoo. {activity_name.capitalize()} ID: {record_id}'
            response_payload = f'{activity_name.capitalize()} updated successfully'

        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)

        self.env['opd_integration.pipedrivelogger'].create_logger(
            '', '', record_direction, module_name, description, record_data,
            response_payload, operation, 'resolve', 'success', record_operation, record_id
        )

    # -------------------------------------- Method To Create Exception Error Logger ----------------------- #

    def exception_log_error(self, error_details, logger_name, description, model_name, operation_type, record_id, error_type='Exception Error'):
        """
        Logs an error in the PipedriveLogger.

        Args:
            error_details (str): The details of the error.
            logger_name (str): The name of the logger (e.g., 'contact', 'company', 'lead', 'deal').
            error_type (str): The type of the error (default is 'Exception Error').
            module_name (str): The name of the module where the error occurred (default is 'contacts').

        Returns:
            None
        """
        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)

        self.env['opd_integration.pipedrivelogger'].create_logger(
            error_details, error_type, record_direction, module_name, description, '', '', '', 'pending', 'error', operation_type, record_id
        )

    # ------------------- Logs an HttpLogError in the PipedriveOdooLogger ------------- #
    def http_log_error(self, error_details, logger_name, description, payload, response, model_name, operation_type, record_id,
                       error_type='Http Error'):
        """
        Logs an HttpLogError in the PipedriveOdooLogger.

        Args:
            error_details (str): The details of the error.
            logger_name (str): The name of the logger (e.g., 'contact', 'company', 'lead', 'deal').
            description (str): A description of the error.
            payload (dict): The payload data sent during the HTTP request.
            response (str): The response received from the HTTP request.
            error_type (str, optional): The type of the error (default is 'Exception Error').

        Returns:
            None
        """
        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)

        self.env['opd_integration.pipedrivelogger'].create_logger(
            error_details, error_type, record_direction, module_name, description, payload, response, '', 'pending',
            'error', operation_type, record_id
        )

    # ------------------------- Schedular Logger Function --------------------------------- #
    def scheduler_run_successfully_log(self, logger_name, operation_type, model_name):
        module_name, record_direction = self.get_module_and_direction(logger_name, model_name)
        logger_name_capitalize = logger_name.capitalize()
        operation_type_capitalize = operation_type.capitalize()
        schedular_direction = 'Pipedrive to Odoo' if model_name == 'odoo' else 'Odoo to Pipedrive'
        operation = f"Create/Update {logger_name_capitalize} in {model_name.capitalize()}"
        description = f"{logger_name_capitalize} {operation_type_capitalize} Run Successfully from {schedular_direction}"
        request_payload = f"Run {logger_name_capitalize} {operation_type_capitalize} from {schedular_direction}"
        response_payload = f"{logger_name_capitalize} {operation_type_capitalize} Run Successfully"

        self.env['opd_integration.pipedrivelogger'].create_logger(
            '', '', record_direction, module_name, description, request_payload,
            response_payload, operation, 'resolve', 'info', operation_type, ''
        )
    # ---------------------- sync_value for the given label_name from the field mapping ------------------ #

    def get_sync_value(self, instance_id, field_model_name, dropdown_field_mapping_name, logger_name, operation_type, label_name='sync_to_odoo'):
        """
            Fetches the sync_value for the given label_name from the field mapping.

            instance_id: The instance containing the dropdown_field_mapping.
            field_model_name: The model name of the fields to search.
            dropdown_field_mapping_name: The name of the dropdown field mapping.
            label_name: The label name to search for, default is 'sync_to_odoo'.

            return : The sync_value corresponding to the 'yes' value, or None if not found.

        """
        fields_lines_data = instance_id.env[field_model_name].search(
            [('pipedrive_fields_record.label_name', '=', label_name)], limit=1)
        if not fields_lines_data:
            description = f"Field Mapping is required for {logger_name.capitalize()}"
            operation = f'{logger_name.capitalize()} Record Sync Pipedrive To Odoo'
            self.log_operation_warning(logger_name, description, operation, 'odoo','',
                                       operation_type, '')
            return None, None

        sync_value, sync_field_id = None, None

        pipedrive_field_data = fields_lines_data['pipedrive_fields_record']
        pipedrive_label_name = pipedrive_field_data.label_name
        if pipedrive_label_name == label_name:
            internal_name = pipedrive_field_data.internal_name
            sync_field_id = pipedrive_field_data.field_id
            dropdown_field = getattr(instance_id, dropdown_field_mapping_name, None)
            if dropdown_field:
                mapping = json.loads(dropdown_field)
                my_dict = mapping.get(internal_name)
                # Directly get the key for 'yes'
                if my_dict:
                    sync_value = next((key for key, value in my_dict.items() if value == 'yes'), None)
        return sync_value, sync_field_id

    # --------------------------------------- Get Field From Mapper using label name -------------------------- #

    def get_field_from_mapper(self, field_mapper_model, label_name, field_name='internal_name'):
        """
        Searches for a record in the specified model based on the label name and returns the value of the specified field.

        Args:
            field_mapper_model (str): The name of the model to search.
            label_name (str): The label name to search for. Defaults to 'odoo_id'.
            field_name (str): The field name whose value needs to be returned. Defaults to 'internal_name'.

        Returns:
            str or None: The value of the specified field if the record is found, otherwise None.
        """
        record = self.env[field_mapper_model].search([('label_name', '=', label_name)], limit=1)
        if record:
            # Accessing the first record in the recordset
            record_field_value = record[field_name]
            return record_field_value
        else:
            # Handling the case where no record is found
            return None

    # --------------- Retrieve the field ID associated with the given internal field name ---------- #

    def get_update_time_field(self, field_model, field_name):
        """
           Retrieve the field ID associated with the given internal field name in the specified model.

           Args:
               field_model (str): The name of the model to search in.
               field_name (str): The internal name of the field to search for.

           Returns:
               int or None: The ID of the field if found, otherwise None.
        """
        record = self.env[field_model].search([('internal_name', '=', field_name)], limit=1)
        if record:
            # Accessing the first record in the recordset
            record_field_id = record.field_id
        else:
            # Handling the case where no record is found
            record_field_id = None
        return record_field_id

    # -------------------- Retrieve the field ID associated with the given label name ----------------- #

    def get_odoo_id_field(self, field_model, field_name):
        """
            Retrieve the field ID associated with the given label name in the specified model.

            Args:
                field_model (str): The name of the model to search in.
                field_name (str): The label name of the field to search for.

            Returns:
                int or None: The ID of the field if found, otherwise None.
        """
        record = self.env[field_model].search([('label_name', '=', field_name)], limit=1)
        if record:
            # Accessing the first record in the recordset
            record_field_id = record.field_id
        else:
            # Handling the case where no record is found
            record_field_id = None

        return record_field_id

    # --------------------------- Get Value Of Pipedrive Email and Phone Field ----------------- #

    def get_field_value(self, data):
        """
        Extracts the 'value' from the given data, which can be a list or dictionary.
        """
        # Check if data is a list and get the 'value' from the first element
        if isinstance(data, list) and data:
            return data[0].get('value')
        # Check if data is a dictionary and contains the 'value' key
        elif isinstance(data, dict) and 'value' in data:
            return data['value']
        else:
            return data

    # ------------------------- Get Pipedrive contact email and phone field value ------------------------ #
    def get_primary_or_first_value(self, record, field_name):
        values = record.get(field_name, [])
        if not isinstance(values, list) or not values:
            return None
        return next(
            (item.get('value') for item in values if item.get('primary')),
            values[0].get('value')
        )

    # ----------------------------------------------
    #   Convert Pipedrive label_ids → Odoo tag_ids
    # ----------------------------------------------
    def map_lead_tags_from_pipedrive(self, record):
        """
        Convert Pipedrive v2 lead label_ids → Odoo crm.tag many2many list.
        Returns list of tag IDs.
        """
        pipedrive_label_ids = record.get("label_ids", [])
        if not pipedrive_label_ids:
            return []

        Tag = self.env['crm.tag']
        odoo_tag_ids = []

        for pd_label_id in pipedrive_label_ids:

            # Try to find existing tag (by pipedrive_id OR name match)
            tag = Tag.search(['|',('pipedrive_id', '=', pd_label_id),('name', '=', pd_label_id)], limit=1)
            if not tag:
                # Create minimal tag (we don't know color without extra API call)
                tag = Tag.create({
                    'name': pd_label_id,
                    'pipedrive_id': pd_label_id
                })
                tag.env.cr.commit()

            odoo_tag_ids.append(tag.id)

        return odoo_tag_ids

    # ------------------------- Field Mapping Function ------------------------ #
    def pipedrive_to_odoo_map_fields(self, record, instance_id, field_model_name, dropdown_mapping_field, record_id, logger_name, operation_type):
        """
        Map Pipedrive fields to Odoo fields using the provided mappings.

        Args: 'pipedriveinstance.companies.lines'
            record (dict): A dictionary containing Pipedrive record data.
            instance_id (str): The Pipedrive instance ID.
            field_model_name (str): The name of the model containing field mappings between Pipedrive and Odoo.
            dropdown_mapping_field (str): The name of the field in `instance_id` containing dropdown mapping information.
        Returns:
            dict: A dictionary containing mapped data for Odoo fields.
        """
        field_mapping = {}
        mapping = {}

        odoo_id_value, operation_status, pipedrive_deal_status = None, None, None

        dropdown_field = getattr(instance_id, dropdown_mapping_field, None)
        # Use the common method to get fields_lines_data
        fields_lines_data = self.get_fields_lines_data(field_model_name, instance_id)

        if dropdown_field:
            mapping = json.loads(dropdown_field)

        if not fields_lines_data:
            description = f"Field Mapping is required for {logger_name.capitalize()}"
            operation = f'{logger_name.capitalize()} Record Sync Pipedrive To Odoo'
            self.log_operation_warning(logger_name, description, operation, 'odoo', record,
                                       operation_type, record_id)
            return None, None, None, None

        for data in fields_lines_data:
            pipedrive_field_data = data['pipedrive_fields_record']
            odoo_field_data = data['odoo_fields_record']
            internal_name = pipedrive_field_data.internal_name
            label_name = odoo_field_data.label_name
            field_mapping[internal_name] = label_name
        record_data = {}

        records = record if isinstance(record, list) else [record]

        for record in records:
            for internal_name, label_name in field_mapping.items():
                record_field_data = None
                # ----------------- Static Handling for Company Address Fields ---------------- #
                if logger_name == 'company' and 'address' in record and isinstance(record.get('address'), dict):
                    address_data = record.get('address', {})
                    if internal_name == 'address':
                        record_field_data = address_data.get('value')  # Full formatted address
                    elif internal_name == 'address_country':
                        record_field_data = address_data.get('country')
                    elif internal_name == 'address_admin_area_level_1':
                        record_field_data = address_data.get('admin_area_level_1')
                    elif internal_name == 'address_locality':
                        record_field_data = address_data.get('locality')
                    elif internal_name == 'address_postal_code':
                        record_field_data = address_data.get('postal_code')

                if logger_name == 'contact':
                    if internal_name == 'phone':
                        record_field_data = self.get_primary_or_first_value(record, 'phones')
                    elif internal_name == 'email':
                        record_field_data = self.get_primary_or_first_value(record, 'emails')

                # ----------------- General Dynamic Field Fetching ---------------- #
                if not record_field_data:
                    record_field_data = (
                            record.get(internal_name)
                            or record.get('custom_fields', {}).get(internal_name)
                    )

                if record_field_data:
                    if label_name == 'state_id':
                        state_name = record_field_data
                        state = self.env['res.country.state'].search([('name', '=', state_name)], limit=1)
                        state_id = state.id
                        if state:
                            record_data[label_name] = state_id
                    elif label_name == 'country_id':
                        country_name = record_field_data
                        country = self.env['res.country'].search([('name', '=', country_name)], limit=1)
                        country_id = country.id
                        if country:
                            record_data[label_name] = country_id
                    elif label_name == 'partner_id':
                        partner_name = record_field_data
                        partner = self.env['res.partner'].search(
                            [('name', '=', partner_name), ('active', '=', True)], limit=1)
                        partner_id = partner.id
                        if partner:
                            record_data[label_name] = partner_id
                    elif label_name == 'id':
                        odoo_id_value = record_field_data
                    # Usage for both phone and email
                    elif label_name == 'phone' or label_name == 'email':
                        field_value = self.get_field_value(record_field_data)
                        record_data[label_name] = field_value if field_value else None
                    elif internal_name == 'stage_id' and record.get('status') in ['won', 'lost']:
                        pipedrive_deal_status = record.get('status')
                        odoo_value = mapping[internal_name].get(pipedrive_deal_status)
                        record_data[label_name] = odoo_value
                    elif internal_name in mapping:
                        organization_value = str(record_field_data)
                        odoo_value = mapping[internal_name].get(organization_value)
                        if odoo_value:
                            record_data[label_name] = odoo_value
                        else:
                            description = (f'Please review and correct the dropdown configuration '
                                           f'{internal_name} mapping as the selected {logger_name} stage does not '
                                           f'match the configured options. Once corrected the {logger_name} '
                                           f'{internal_name}, and please try again. {logger_name} ID: {record_id}')
                            operation = f'{logger_name} send pipedrive to odoo'
                            operation_status = 'skip'
                            self.log_operation_warning(logger_name, description, operation, 'odoo', record, operation_type, record_id)
                            continue
                    else:
                        record_data[label_name] = record_field_data
                else:
                    record_data[label_name] = None
                    if label_name == 'probability':
                        record_data[label_name] = float('0.0')
                    if label_name == 'list_price':
                        # Assuming prices is a list of dictionaries
                        prices = record.get('prices', [])
                        if prices:
                            price = prices[0].get('price') if isinstance(prices, list) else prices.get('price')
                            record_data[label_name] = price
                    if logger_name == 'product':
                        # Assuming prices is a list of dictionaries
                        prices = record.get('prices', [])
                        if prices:
                            price = prices[0].get('cost') if isinstance(prices, list) else prices.get('cost')
                            record_data['standard_price'] = price
                    if label_name == 'categ_id':
                        description = (f'Please review and correct the dropdown configuration '
                                       f'{internal_name} mapping as the selected {logger_name} does not '
                                       f'match the configured options. Once corrected the {logger_name} '
                                       f'{internal_name}, and please try again. {logger_name} ID: {record_id}')
                        operation = f'{logger_name} send pipedrive to odoo'
                        self.log_operation_warning(logger_name, description, operation, 'odoo', record, operation_type, record_id)
                        operation_status = 'skip'
                        continue
            if logger_name == 'deal':
                # If Pipedrive marks deal as Won → always force 100 in Odoo
                if pipedrive_deal_status == 'won':
                    record_data['probability'] = 100.0

                # If Pipedrive marks deal as Lost → always force 0 in Odoo
                elif pipedrive_deal_status == 'lost':
                    record_data['probability'] = 0.0

                # Check and validate the probability field
                elif 'probability' in record_data and record_data['probability'] is not None:
                    probability = record_data['probability']
                    if probability > 100:
                        magnitude = len(str(int(probability))) - 2
                        probability /= 10 ** magnitude
                        probability = round(probability, 2)
                    record_data['probability'] = probability

            # ----------------------------------------------------------
            #  SPECIAL HANDLING FOR LEAD TAGS (label_ids field)
            # ----------------------------------------------------------
            if logger_name == 'lead':
                tag_ids = self.map_lead_tags_from_pipedrive(record)
                if tag_ids:
                    # Assign to M2M field in Odoo → replace all tags
                    record_data['tag_ids'] = [(6, 0, tag_ids)]

            mapped_data = self.prepare_mapped_data_pipedrive_and_odoo(record_data, mapping)

            pipeline_id = record.get('pipeline_id')  # Safely get the pipeline_id
            if pipeline_id:
                if mapping.get('pipeline_id'):
                    odoo_team_id = mapping['pipeline_id'].get(str(pipeline_id))
                    if odoo_team_id:
                        record_data['team_id'] = odoo_team_id

            # Fields to exclude
            exclude_fields = ['list_price', 'standard_price', 'tag_ids']

            # Filter out the fields to exclude
            filtered_mapped_data = {k: v for k, v in mapped_data.items() if k not in exclude_fields}
            dynamic_fields_values_hash = self.calculate_hash(filtered_mapped_data)
            return record_data, odoo_id_value, dynamic_fields_values_hash, operation_status
        return None, None, None, None

    # ----------------------------- Fetch Last Sync Date and Current UTC Time ---------------------------- #

    def last_sync_date_common(self, last_sync_date_field):
        # Set a temporary variable to store the current UTC time at the start of the function
        current_utc_time = datetime.utcnow()

        user_timezone = self.env.user.tz or 'UTC'

        # Get the current IST time
        now_ist = datetime.now(pytz.timezone(user_timezone))

        # Convert IST time to UTC time
        now_utc = now_ist.astimezone(pytz.utc)
        last_sync_date = last_sync_date_field
        if not last_sync_date:
            # First sync: use current UTC as temporary filter baseline only.
            # The instance last-sync field stays empty until sync completes and writes current_utc_time.
            # Customers may also set last sync date manually before running sync.
            last_sync_date = now_utc.replace(tzinfo=None)
        return last_sync_date, current_utc_time

    # -------------------------------------- Check Field Mappings ------------------------------- #

    def has_field_mappings(self, field_model_name, instance_id, logger_name, operation_type):
        # Step 1: Fetch field mappings from the specified model
        field_mappings = self.get_fields_lines_data(field_model_name, instance_id)
        if not field_mappings:
            # Log the operation warning with specific details
            description = f"Field Mapping is required for {logger_name.capitalize()}"
            operation = f'{logger_name.capitalize()} Record Sync Pipedrive To Odoo'
            self.log_operation_warning(logger_name, description, operation, 'odoo', '',
                                       operation_type, '')
            # Return False if no mappings are found
            return False
        # Return True if mappings are found
        return True

    # ------------------------- Fetch Data From Pipedrive And Send To Odoo Function (v2 Compatible) ------------------------ #
    @api.model
    def fetch_partner_data_from_pipedrive(self, instance_id, pipedrive_model_name, odoo_model_name, field_model_name,
         field_mapper_model,last_sync_date_field,calls_field, tasks_field, emails_field, meetings_field, notes_field,
         type, object, is_company, dropdown_field_mapping_name, logger_name,operation_type):

        """
        Fetches data from Pipedrive (v2 API) based on the provided model name,
        updates records in Odoo, and handles cursor-based pagination.

        Args:
            instance_id (record): The Pipedrive instance record.
            pipedrive_model_name (str): Pipedrive model name ('persons', 'organizations', etc.).
            odoo_model_name (str): Corresponding Odoo model name ('res.partner', etc.).
            field_model_name (str): Mapper model name.
            field_mapper_model (str): Field mapper model.
            last_sync_date_field (datetime): The last synchronization date field.
            calls_field, tasks_field, emails_field, meetings_field, notes_field (str): Related fields.
            type, object (str): Pipedrive type identifiers.
            is_company (bool): Whether record is a company.
            dropdown_field_mapping_name (str): Dropdown mapping field.
            logger_name, operation_type (str): Logging details.
        """

        try:
            if not self.get_validated_api_base_url(instance_id, logger_name, operation_type):
                return
            # ---------------------- Get Sync Dates ---------------------- #
            last_sync_date, current_utc_time = self.last_sync_date_common(last_sync_date_field)

            # Convert last_sync_date → RFC3339 format for Pipedrive v2
            updated_since = (
                last_sync_date.strftime('%Y-%m-%dT%H:%M:%SZ') if last_sync_date else None
            )
            # Convert both formats for clarity
            filter_date_value = last_sync_date.strftime('%Y-%m-%d')  # For filter creation
            # Identify record tracking fields
            record_last_id = (
                instance_id.pipedrive_company_last_id
                if is_company
                else instance_id.pipedrive_contact_last_id
            )
            # Set pagination and authentication
            limit = instance_id.pagination_size  # Pipedrive v2 max recommended
            cursor = None
            api_token = instance_id.api_token

            # Ensure field mapping is configured
            is_field_mapping = self.has_field_mappings(field_model_name, instance_id, logger_name, operation_type)
            if not is_field_mapping:
                return

            # ---------------------- Main Fetch Loop ---------------------- #
            while True:
                sync_value, sync_field_id = self.get_sync_value(
                    instance_id, field_model_name, dropdown_field_mapping_name, logger_name, operation_type
                )
                update_time_value = self.get_update_time_field(field_mapper_model, 'update_time')
                last_field_id = self.get_update_time_field(field_mapper_model, 'id')
                if last_sync_date and sync_value:
                    # Create dynamic filter using v1 logic (for last_record_id)
                    filter_id = self.env['opd.mapper.mixin'].fetch_filter_id(
                        api_token,filter_date_value,  # ✅ RFC3339 formatted date
                        sync_value,update_time_value,sync_field_id,
                        type,object,logger_name,last_field_id,record_last_id,operation_type)
                else:
                    break

                # ---------------------- Build Endpoint ---------------------- #
                endpoint = (
                    f"{instance_id.api_base_url}/{pipedrive_model_name}"
                    f"?filter_id={filter_id}"
                    f"&limit={limit}"
                    f"&updated_since={updated_since}"
                    f"&sort_by=id&sort_direction=asc"
                    f"&api_token={api_token}"
                )
                # Add cursor if paginated
                if cursor:
                    endpoint += f"&cursor={cursor}"

                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

                # ---------------------- API Call ---------------------- #
                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, {}, method="GET")
                if response.status_code != 200:
                    self.http_log_error(
                        f"No record found: {response.text}", logger_name,
                        "Error occurred while fetching records",
                        {}, response.text, 'odoo', operation_type, '', f"HTTP {response.status_code}"
                    )
                    break

                response_json = response.json()
                partner_records = response_json.get('data', [])
                additional_data = response_json.get('additional_data', {})
                # ✅ v2-style pagination
                cursor = additional_data.get('next_cursor')
                # ---------------------- Process Records ---------------------- #
                if partner_records:
                    if odoo_model_name == 'res.partner':
                        if not is_company:
                            self.process_partner_contact(
                                partner_records, instance_id, odoo_model_name,
                                calls_field, tasks_field, emails_field, meetings_field,
                                notes_field, api_token, logger_name, field_model_name,
                                pipedrive_model_name, dropdown_field_mapping_name,
                                operation_type, check_hash=True
                            )
                        else:
                            self.process_partner_company(
                                partner_records, instance_id, odoo_model_name,
                                calls_field, tasks_field, emails_field, meetings_field,
                                notes_field, api_token, logger_name, field_model_name,
                                pipedrive_model_name, dropdown_field_mapping_name,
                                operation_type, check_hash=True
                            )

                    # Update last processed ID
                    record_last_id = partner_records[-1].get('id')
                    if is_company:
                        instance_id.write({'pipedrive_company_last_id': record_last_id})
                    else:
                        instance_id.write({'pipedrive_contact_last_id': record_last_id})
                    instance_id.env.cr.commit()

                # ---------------------- Stop Condition ---------------------- #
                if not cursor:
                    break

            # ---------------------- Final Sync State Update ---------------------- #
            if pipedrive_model_name == 'organizations':
                instance_id.write({
                    'pipedrive_company_last_sync_date': current_utc_time,
                    'pipedrive_company_last_id': 0
                })
            elif pipedrive_model_name == 'persons':
                instance_id.write({
                    'pipedrive_contact_last_sync_date': current_utc_time,
                    'pipedrive_contact_last_id': 0
                })

            self.scheduler_run_successfully_log(logger_name, operation_type, 'odoo')

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} Create/Update in the Odoo.'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)

    # --------------------------- Create Or Update Pipedrive Contact In Odoo ----------------------- #
    def process_partner_contact(self, batch_records, instance_id, odoo_model_name,
        calls_field, tasks_field, emails_field, meetings_field, notes_field,api_token,logger_name, field_model_name,
        pipedrive_model_name, dropdown_field_mapping_name, operation_type, check_hash=True):
        """
                Processes contact records.

                Args:
                    record (dict): The record data from Pipedrive.
                    record_data (dict): The mapped record data for Odoo.
                    dynamic_fields_values_hash (str): The hash of dynamic field values.
                    instance_id (str): The Pipedrive instance ID.
                    odoo_model_name (str): The name of the Odoo model.
                    record_id (int): The record ID from Pipedrive.
                    calls_field (str): The field name for calls.
                    tasks_field (str): The field name for tasks.
                    emails_field (str): The field name for emails.
                    meetings_field (str): The field name for meetings.
                    notes_field (str): The field name for notes.
                    api_token (str): The API token for Pipedrive.
                    check_hash(Bool): Check Odoo Hash based on Check hash True or False
                Returns:
                    None
                """
        operation_status = None
        for contact in batch_records:
            record_id = contact.get('id')
            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(contact,
                       instance_id,field_model_name,dropdown_field_mapping_name,record_id,logger_name, operation_type)
            if operation_status == 'skip':
                continue
            if record_data:
                record_data['pipedrive_id'] = record_id
                user_record = self.get_odoo_user_from_pipedrive_record(contact)
                pipedrive_user_id = user_record.id if user_record else None
                record_data['odoo_hash'] = dynamic_fields_values_hash
                record_data['is_company'] = False
                if user_record:
                    record_data['user_id'] = user_record.id
                email = record_data.get('email')
                sync_field = self.get_field_from_mapper('opd.contactmapper', 'odoo_id',
                                                        field_name='internal_name')
                odoo_id = self._get_pipedrive_custom_field_value(contact, sync_field)
                org_id = contact['org_id'] if contact.get('org_id') is not None else None
                partner, email_exists_with_pipedrive_id = self.search_partner(email, odoo_id, False)

                if email_exists_with_pipedrive_id:
                    description = f'The email ID {email} is already associated with another contact [{partner.name}] with a Pipedrive ID {partner.pipedrive_id}. Please use a different email ID.'
                    operation = 'Contact send pipedrive to odoo'
                    self.log_operation_warning(logger_name, description, operation, 'odoo', contact, operation_type, record_id)
                    operation_status = 'skip'
                    continue

                if partner and not email_exists_with_pipedrive_id:
                    if not check_hash or partner.odoo_hash != dynamic_fields_values_hash:
                        partner_user_id = partner.user_id.id
                        if partner_user_id == pipedrive_user_id:
                            record_data.pop('user_id', None)
                        else:
                            record_data = record_data
                        partner.write(record_data)
                        partner.env.cr.commit()
                        self.log_operation(logger_name, '', record_id, record_data, 'update', 'odoo', operation_type, parent_name=None,
                                           parent_id=None)
                        self.pipedrive_update_odoo_id(record_id, partner,
                                                      pipedrive_model_name, api_token, logger_name, operation_type)
                        self.process_contact_related_modules(instance_id, record_id, api_token, logger_name, operation_type, org_id)
                        self.fetch_activity(instance_id, partner, odoo_model_name, calls_field, tasks_field, emails_field,
                                            meetings_field, notes_field, 'persons', record_id, api_token, logger_name, operation_type,
                                            check_hash)

                        operation_status = 'update'

                    else:
                        operation_status = 'no_update'
                elif not partner:
                    odoo_record = self.env['res.partner'].create(record_data)
                    odoo_record.env.cr.commit()
                    self.log_operation(logger_name, '', record_id, record_data, 'create', 'odoo', operation_type, parent_name=None,
                                       parent_id=None)
                    self.pipedrive_update_odoo_id(record_id, odoo_record,
                                                  pipedrive_model_name, api_token, logger_name, operation_type)
                    self.process_contact_related_modules(instance_id, record_id, api_token, logger_name, operation_type, org_id)
                    self.fetch_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field, emails_field,
                                        meetings_field, notes_field, 'persons', record_id, api_token, logger_name, operation_type,
                                        check_hash)

                    operation_status = 'create'
        return operation_status

    # ------------------ Update Or Create Company Records In Odoo ---------------- #
    def process_partner_company(self, batch_records, instance_id,odoo_model_name,
        calls_field, tasks_field, emails_field, meetings_field, notes_field,api_token,
        logger_name, field_model_name, pipedrive_model_name, dropdown_field_mapping_name, operation_type,
        check_hash=True):
        """
            Process and update or create company records in Odoo, and fetch related activities, contacts, leads, and deals from Pipedrive.

            Args:
                record_data (dict): The data for the company record.
                dynamic_fields_values_hash (str): The hash value of dynamic fields to check if updates are needed.
                instance_id: The Pipedrive instance ID.
                odoo_record: The existing Odoo record if it exists.
                odoo_model_name (str): The name of the Odoo model for companies.
                record_id (int): The ID of the Pipedrive record.
                calls_field (str): The field name for calls.
                tasks_field (str): The field name for tasks.
                emails_field (str): The field name for emails.
                meetings_field (str): The field name for meetings.
                notes_field (str): The field name for notes.
                api_token (str): The API token for authentication.
                check_hash(Bool): Check Odoo Hash based on Check hash True or False
            Returns:
                None
                :param batch_records:
        """
        operation_status = None
        for company in batch_records:
            record_id = company.get('id')
            # Iterate over the field mappings
            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(company,
            instance_id,field_model_name,dropdown_field_mapping_name,record_id,logger_name, operation_type)
            if operation_status == 'skip':
                continue
            if record_data:
                record_data['pipedrive_id'] = record_id
                user_record = self.get_odoo_user_from_pipedrive_record(company)
                pipedrive_user_id = user_record.id if user_record else None
                record_data['odoo_hash'] = dynamic_fields_values_hash
                record_data['is_company'] = True

                # check that pipedrive record is exist in odoo
                odoo_record = self.env[odoo_model_name].search(
                    [('pipedrive_id', '=', record_id), ('is_company', '=', True),
                     ('active', '=', True)], limit=1)
                if user_record:
                    record_data['user_id'] = user_record.id
                if not odoo_record:
                    odoo_record = self.env[odoo_model_name].create(record_data)
                    odoo_record.env.cr.commit()
                    self.log_operation(logger_name, '', record_id, record_data, 'create', 'odoo', operation_type, parent_name=None,
                                       parent_id=None)
                    self.pipedrive_update_odoo_id(record_id, odoo_record,
                                                  pipedrive_model_name, api_token, logger_name, operation_type)
                    # Process related modules regardless of whether the record was created or updated
                    self.process_company_related_modules(instance_id, record_id, odoo_model_name, api_token, logger_name, operation_type)
                    self.fetch_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field, emails_field,
                                        meetings_field, notes_field, 'organizations', record_id, api_token, logger_name, operation_type,
                                        check_hash)

                    operation_status = 'create'

                elif odoo_record:
                    if not check_hash or odoo_record.odoo_hash != dynamic_fields_values_hash:
                        partner_user_id = odoo_record.user_id.id
                        if partner_user_id == pipedrive_user_id:
                            record_data.pop('user_id', None)
                        else:
                            record_data = record_data
                        odoo_record.write(record_data)
                        self.log_operation(logger_name, '', record_id, record_data, 'update', 'odoo', operation_type, parent_name=None,
                                           parent_id=None)
                        self.pipedrive_update_odoo_id(record_id, odoo_record,
                                                      pipedrive_model_name, api_token, logger_name, operation_type)
                        # Process related modules regardless of whether the record was created or updated
                        self.process_company_related_modules(instance_id, record_id, odoo_model_name, api_token,
                                                             logger_name, operation_type)
                        self.fetch_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
                        emails_field,meetings_field, notes_field, 'organizations', record_id,
                        api_token, logger_name, operation_type,check_hash)

                        operation_status = 'update'
                    else:
                        operation_status = 'no_update'
        return operation_status

    # ------------------------ Retrieve the internal name of the field  ----------------------- #

    def get_sync_to_odoo(self, field_mapper_model):

        """
            Retrieve the internal name of the field used for synchronization to Odoo.

            This function searches the specified field mapper model for the 'sync_to_odoo' label
            and returns the corresponding internal name.

            field_mapper_model: The model used for field mapping.

            return: The internal name of the field used for synchronization to Odoo.
        """
        record = self.env[field_mapper_model].search([('label_name', '=', 'sync_to_odoo')])
        field_name = record.internal_name
        return field_name

    # ---------------------------- Company Related Module Function Call Method ------------------ #

    def process_company_related_modules(self, instance_id, record_id, odoo_model_name, api_token, logger_name, operation_type):
        """
        Process related modules for a given record ID.

        Args:
            instance_id: The Pipedrive instance ID.
            record_id (int): The ID of the Pipedrive record.
            odoo_model_name (str): The name of the Odoo model.
            api_token (str): The API token for authentication.
            logger_name (str): The logger name for logging purposes.

        Returns:
            None
        """
        if instance_id.pipedrive_company_related_contacts and record_id:
            self.pipedrive_company_related_contacts(
                instance_id, record_id, 'persons', odoo_model_name, api_token,
                'persons', True, 'pipedriveinstance.contacts.lines',
                'pipedrive_contacts_dropdown_mapping', logger_name, operation_type
            )

        if instance_id.pipedrive_company_related_leads and record_id:
            self.pipedrive_partner_related_leads(
                instance_id, record_id, api_token, 'crm.lead', 'leads', True,
                'pipedriveinstance.leads.lines', 'pipedrive_lead_dropdown_mapping',
                'related_org_id', 'leads', 'lead', logger_name, operation_type
            )

        if instance_id.pipedrive_company_related_deals and record_id:
            self.pipedrive_partner_related_deals(
                instance_id, 'deals', 'org_id', 'crm.lead', record_id, api_token,
                'deals', True, 'pipedriveinstance.deals.lines',
                'pipedrive_deal_dropdown_mapping', logger_name, operation_type
            )

        # ---------------------------- Contact Related Module Function Call Method ------------------ #

    def process_contact_related_modules(self, instance_id, record_id, api_token, logger_name, operation_type, org_id=None):
        """
        Process related modules for a given record ID.

        Args:
            instance_id: The Pipedrive instance ID.
            record_id (int): The ID of the Pipedrive record.
            odoo_model_name (str): The name of the Odoo model.
            api_token (str): The API token for authentication.
            logger_name (str): The logger name for logging purposes.

        Returns:
            None
        """
        if instance_id.pipedrive_contact_related_companies:
            self.pipedrive_contact_related_companies(
                instance_id, org_id, record_id, 'organizations', api_token,
                'res.partner', 'pipedriveinstance.companies.lines',
                'pipedrive_company_dropdown_mapping', logger_name
            , operation_type)

        if instance_id.pipedrive_contact_related_deals and record_id:
            self.pipedrive_partner_related_deals(
                instance_id, 'deals', 'person_id','crm.lead', record_id, api_token,
                'deals', False, 'pipedriveinstance.deals.lines',
                'pipedrive_deal_dropdown_mapping', logger_name
            , operation_type)

        if instance_id.pipedrive_contact_related_leads and record_id:
            self.pipedrive_partner_related_leads(
                instance_id, record_id, api_token, 'crm.lead', 'leads', False,
                'pipedriveinstance.leads.lines', 'pipedrive_lead_dropdown_mapping',
                'related_person_id', 'leads', 'lead', logger_name
            , operation_type)

    # ---------------- Check Existing Partner In Odoo By Email Or Odoo ID ---------------- #
    def search_partner(self, email, odoo_id, is_company):
        """
           Search for an existing partner in Odoo by email or Odoo ID.

           Args:
               email (str): The email of the partner.
               odoo_id (int): The Odoo ID of the partner.
               is_company (bool): Flag indicating whether the partner is a company.

           Returns:
               partner: The found partner record or False if no partner is found.
        """
        partner, email_exists_with_pipedrive_id = False, False
        if email and odoo_id:
            partner = self.env['res.partner'].search(
                [('id', '=', odoo_id), ('is_company', '=', is_company), ('active', '=', True)],limit=1)
        elif odoo_id:
            partner = self.env['res.partner'].search(
                [('id', '=', odoo_id), ('is_company', '=', is_company), ('active', '=', True)], limit=1)
        elif email:
            partner = self.env['res.partner'].search(
                [('email', '=', email), ('is_company', '=', is_company), ('active', '=', True)], limit=1,
                order="pipedrive_id ASC")
            if partner and partner.pipedrive_id:
                email_exists_with_pipedrive_id = True
        return partner, email_exists_with_pipedrive_id

    # ---------------- Check Existing Product In Odoo By Default Code Or Odoo ID ---------------- #

    def search_product(self, default_code, odoo_id):
        """
           Search for an existing partner in Odoo by Default Code or Odoo ID.

           Args:
               default_code (str): The internal reference of the product.
               odoo_id (int): The Odoo ID of the product.

           Returns:
               product: The found product record or False if no product is found.
        """
        product, default_code_exists_with_pipedrive_id = False, False
        if default_code and odoo_id:
            product = self.env['product.template'].search([('id', '=', odoo_id), ('active', '=', True)],limit=1)
        elif odoo_id:
            product = self.env['product.template'].search([('id', '=', odoo_id), ('active', '=', True)], limit=1)
        elif default_code:
            product = self.env['product.template'].search(
                [('default_code', '=', default_code), ('active', '=', True)], limit=1)
            if product and product.pipedrive_id:
                default_code_exists_with_pipedrive_id = True
        return product, default_code_exists_with_pipedrive_id

    # ------------------------ Get Field Lines Data Based On Field Model Name ---------------- #

    def get_fields_lines_data(self, field_model_name, instance_id):
        """
        Get field lines data based on the field model name and current instance ID.

        Args:
            field_model_name (str): The name of the model containing field mappings between Pipedrive and Odoo.
            instance_id (recordset): The instance ID of the Pipedrive instance.

        Returns:
            recordset: The field lines data.
        """
        FIELD_MODEL_MAPPER = {
            'pipedriveinstance.contacts.lines': 'contactmapper_id',
            'pipedriveinstance.leads.lines': 'leadmapper_id',
            'pipedriveinstance.deals.lines': 'dealmapper_id',
            'pipedriveinstance.products.lines': 'productmapper_id',
            'pipedriveinstance.companies.lines': 'companymapper_id',
        }

        # Get the appropriate mapper field name based on the field_model_name
        mapper_field_name = FIELD_MODEL_MAPPER.get(field_model_name)
        if not mapper_field_name:
            raise ValueError(f"No mapper field name found for field model name: {field_model_name}")

        # Search for field lines data using the dynamically determined mapper field name
        fields_lines_data = self.env[field_model_name].search([(mapper_field_name, '=', instance_id.id)])
        return fields_lines_data

    # ---------------------- Prepare the mapped data dictionary ------------------------- #

    @api.model
    def prepare_mapped_data_pipedrive_and_odoo(self, mapped_data, mapping=None):
        """
               Prepares the mapped data dictionary by handling float-to-string conversions
               and stripping trailing zeros. Converts float fields to integers if they
               end with ".00" or ".0".

               Args:
                   temp_data (dict): The temporary data dictionary to be processed.

               Returns:
                   dict: The processed mapped data dictionary.
               """
        if mapping:
            mapped_data = {
                key: mapping[key][value] if key in mapping and value in mapping[key] and key != 'stage_id' else value
                for key, value in mapped_data.items()
            }
        else:
            mapped_data = {key: value for key, value in mapped_data.items()}

        for key, value in mapped_data.items():
            if isinstance(value, float):
                mapped_data[key] = "{:.2f}".format(value).rstrip('0').rstrip('.')

        # Convert float fields to integers if they end with ".00"
        for key, value in mapped_data.items():
            if isinstance(value, str) and value.endswith('.00'):
                try:
                    mapped_data[key] = int(float(value))
                except ValueError:
                    pass  # Ignore conversion errors

            if isinstance(value, str) and value.endswith('.0'):
                try:
                    mapped_data[key] = int(float(value))
                except ValueError:
                    pass  # Ignore conversion errors

        return mapped_data

    # -------------------------- Create Odoo Hash ------------------- #
    @api.model
    def calculate_hash(self, mapped_data):
        """
            Calculates the SHA-256 hash of the concatenated values in the mapped data
            dictionary.

            Args:
                mapped_data (dict): The mapped data dictionary whose values will be
                                    concatenated and hashed.

            Returns:
                str: The SHA-256 hash of the concatenated values.
        """
        joined_value = ''.join(str(value) for value in mapped_data.values())
        dynamic_fields_values_hash = hashlib.sha256(str(joined_value).encode()).hexdigest()
        return dynamic_fields_values_hash

    # -------------- Update Record In Pipedrive With The Odoo ID ----------------- #
    def update_pipedrive_organization(self, api_token, pipedrive_model_name, organization_id, internal_name,
                                      partner_id):
        """
            Update an organization record in Pipedrive with the given internal name and partner ID.

            Args:
                api_token (str): The API token for authentication.
                pipedrive_model_name (str): The name of the Pipedrive model (e.g., 'organizations', 'leads').
                organization_id (int): The ID of the Pipedrive organization to update.
                internal_name (str): The internal field name to update in Pipedrive.
                partner_id (int): The partner ID to be set in the specified internal field.

            Returns:
                dict: The JSON response from the Pipedrive API.
            """
        instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)

        if pipedrive_model_name == 'leads':
            url = f"https://api.pipedrive.com/v1/{pipedrive_model_name}/{organization_id}?api_token={api_token}"
            payload = json.dumps({
                internal_name: str(partner_id)
            })
        else:
            url = f"{instance_id.api_base_url}/{pipedrive_model_name}/{organization_id}?api_token={api_token}"
            payload = json.dumps({
                'custom_fields': {
                    internal_name: str(partner_id)
                }
            })

        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

        if pipedrive_model_name == 'leads':
            response = requests.request("PATCH", url, headers=headers, data=payload)
        else:
            response = requests.request("PATCH", url, headers=headers, data=payload)
        return response.json()

    # ------------------------- Update Record In Pipedrive With The Odoo ID ----------------- #
    def pipedrive_update_odoo_id(self, record_id, odoo_record, pipedrive_model_name,
                                 api_token, logger_name, operation_type):
        """
        Update Pipedrive organization with partner ID.

        Args:
            record_id (str): The Pipedrive ID of the record.
            odoo_model_name (str): The name of the Odoo model.
            field_model_name (str): The name of the field model containing mappings.
            api_token (str): The Pipedrive API token.

        Returns:
            None
        """
        field_mapper_model = None
        if logger_name == 'company':
            field_mapper_model = 'opd.companymapper'
        elif logger_name == 'contact':
            field_mapper_model = 'opd.contactmapper'
        elif logger_name == 'lead':
            field_mapper_model = 'opd.leadmapper'
        elif logger_name == 'deal':
            field_mapper_model = 'opd.dealmapper'
        elif logger_name == 'product':
            field_mapper_model = 'opd.productmapper'

        partner_id = odoo_record.id
        sync_field = self.get_field_from_mapper(field_mapper_model, 'odoo_id',
                                                field_name='internal_name')
        if sync_field:
            response = self.update_pipedrive_organization(api_token,pipedrive_model_name,
                  record_id,sync_field, partner_id)

            # Process the response
            if response.get('success'):
                _logger.info(f"Organization {record_id} updated successfully with partner ID {partner_id}")
            else:
                status_code = response.get('status_code')
                reason = response.get('reason')
                error_details = f"{status_code} - {reason}"
                description = f"Failed to update odoo_id in pipedrive"
                self.http_log_error(error_details, logger_name, description, {}, response.get('text'),
                                    'odoo', operation_type, record_id, f"HTTP {status_code}")

    # ---------------------------- Company Related Contacts -------------------------- #

    def pipedrive_company_related_contacts(self, instance_id, record_id, pipedrive_model_name, odoo_model_name,
        api_token,contact_model, is_company, field_model_name, dropdown_field_mapping_name,
        logger_name, operation_type):
        """
           Fetch and process related contacts for a company from Pipedrive, and update or create corresponding records in Odoo.

           Args:
               instance_id: The Pipedrive instance ID.
               record_id (int): The ID of the Pipedrive company record.
               pipedrive_model_name (str): The name of the Pipedrive model (e.g., 'organizations').
               odoo_model_name (str): The name of the corresponding Odoo model (e.g., 'res.partner').
               api_token (str): The API token for authentication.
               contact_model (str): The name of the Pipedrive contact model (e.g., 'persons').
               is_company (bool): Flag to indicate if the record is a company.
               field_model_name (str): The name of the model containing field mappings between Pipedrive and Odoo.
               dropdown_field_mapping_name (str): The name of the dropdown field mapping.

           Returns:
               None
           """
        contact_id = None
        try:
            contact_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?org_id={record_id}&api_token={api_token}"

            contact_payload = {}
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            contact_response = self.env['opd.mapper.mixin'].fetch_data(contact_endpoint, headers,contact_payload, method="GET")
            company = self.env[odoo_model_name].search(
                [('pipedrive_id', '=', record_id), ('is_company', '=', is_company), ('active', '=', True)], limit=1)
            company_id = company.id

            if contact_response and contact_response.status_code == 200:
                response_json = contact_response.json()
                contacts_data = response_json.get('data')

                if contacts_data:  # Check if contacts_data

                    # Iterate through the fetched contacts
                    for contact_data in contacts_data:
                        contact_id = contact_data.get('id')
                        sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                         dropdown_field_mapping_name, 'contact', operation_type)
                        if not sync_value:
                            continue
                        sync_value = int(sync_value)
                        sync_field = self.get_field_from_mapper('opd.contactmapper',
                          'sync_to_odoo',field_name='internal_name')
                        sync_field_name = self._get_pipedrive_custom_field_value(contact_data, sync_field)
                        if sync_field_name:
                            sync_field_name = int(sync_field_name)
                        if sync_field_name == sync_value:
                            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                contact_data, instance_id,field_model_name,dropdown_field_mapping_name,contact_id,
                                'contact', operation_type)
                            if operation_status == 'skip':
                                continue
                            if record_data:
                                record_data['pipedrive_id'] = contact_id
                                record_data['odoo_hash'] = dynamic_fields_values_hash
                                record_data['is_company'] = False
                                # record_data['sync_to_pipedrive'] = True

                                email = contact_data.get('primary_email')

                                sync_field = self.get_field_from_mapper('opd.contactmapper', 'odoo_id',
                                                                        field_name='internal_name')
                                odoo_id = self._get_pipedrive_custom_field_value(contact_data, sync_field)
                                partner, email_exists_with_pipedrive_id = self.search_partner(email, odoo_id, False)

                                if email_exists_with_pipedrive_id:
                                    description = f'The email ID {email} is already associated with another contact [{partner.name}] with a Pipedrive ID {partner.pipedrive_id}. Please use a different email ID.'
                                    operation = 'Contact send pipedrive to odoo'
                                    self.log_operation_warning(logger_name, description, operation, 'odoo', contact_data, operation_type, record_id)
                                    # Link the existing contact to the deal
                                    continue

                                if partner and not email_exists_with_pipedrive_id:
                                    company_id_int = int(company_id)
                                    partner.write({'parent_id': company_id_int})
                                    partner.env.cr.commit()
                                    self.log_operation('contact', '', contact_id, record_data, 'update', 'odoo', operation_type,
                                                       logger_name,record_id)
                                    self.pipedrive_update_odoo_id(contact_id, partner,
                                                                  contact_model, api_token, 'contact', operation_type)
                                else:
                                    # Extract user record using "owner_id"
                                    user_record = self.env['res.users'].get_user_record(contact_data, "owner_id")
                                    if user_record:
                                        record_data['user_id'] = user_record.id
                                    odoo_record = self.env['res.partner'].create(record_data)
                                    odoo_record.env.cr.commit()
                                    if odoo_record:
                                        company_id_int = int(company_id)
                                        odoo_record.write({'parent_id': company_id_int})
                                        odoo_record.env.cr.commit()
                                        self.log_operation('contact', '', contact_id, record_data,
                                        'create', 'odoo', operation_type,logger_name,record_id)
                                        self.pipedrive_update_odoo_id(contact_id, odoo_record,
                                           contact_model, api_token, 'contact', operation_type)
                        else:
                            continue

            else:
                error_details = f"{contact_response.status_code} - {contact_response.reason}"
                description = f"Failed to fetch Pipedrive {pipedrive_model_name} data."
                self.http_log_error(error_details, 'contact', description, contact_payload, contact_response.text,
                                    'odoo', operation_type, contact_id, f"HTTP {contact_response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related contacts for company ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'contact', description, 'odoo', operation_type, contact_id, error_type)

    # ------------------------------ Company And Contact Related Leads ------------------------------- #

    def pipedrive_partner_related_leads(self, instance_id, record_id, api_token, odoo_model_name,
                                        contact_model, is_company, field_model_name, dropdown_field_mapping_name,
                                        field_name, type, object, logger_name, operation_type):
        """
            Description:
                Synchronizes leads related to a company and contact between Pipedrive and Odoo.

            Args: instance_id: The Pipedrive instance ID. record_id: The ID of the record in Pipedrive. api_token:
            Pipedrive API token. odoo_model_name: The name of the Odoo model. contact_model: The name of the contact
            model. is_company: Boolean indicating whether the record is a company. field_model_name: The name of the
            model containing field mappings between Pipedrive and Odoo. dropdown_field_mapping_name: The name of the
            field in `instance_id` containing dropdown mapping information. field_id: The ID of the field. type: The
            type of the field. object: The object type.

            Returns:
                None
            """
        partner_id, pipedrive_id = None, None
        try:
            sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name, dropdown_field_mapping_name, 'lead', operation_type)
            related_person_org_value = self.get_update_time_field('opd.leadmapper', field_name)
            # filter check that related person or organization link with any leads
            if sync_value and record_id:
                filter_id = self.fetch_crm_filter_id(api_token, record_id, sync_value, related_person_org_value,
                                                     sync_field_id, type, object, logger_name, operation_type)
            else:
                return

            data_endpoint = f'{self.__API_BASE_URL}{contact_model}/?archived_status=not_archived&filter_id={filter_id}&api_token={api_token}'
            data_payload = {}
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            response = self.fetch_data(data_endpoint, headers, data_payload, method="GET")
            partner_record = self.env['res.partner'].search(
                [('pipedrive_id', '=', record_id), ('is_company', '=', is_company), ('active', '=', True)], limit=1)

            if partner_record:
                partner_id = partner_record.id

            if response and response.status_code == 200:
                response_json = response.json()
                response_data = response_json.get('data')
                if response_data:  # Check if contacts_data is not None

                    # Iterate through the fetched contacts
                    for lead_data in response_data:
                        try:
                            sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                            dropdown_field_mapping_name, 'lead', operation_type)
                            if not sync_value:
                                continue
                            sync_value = int(sync_value)
                            sync_field = self.get_field_from_mapper('opd.leadmapper', 'sync_to_odoo',
                                                                    field_name='internal_name')
                            sync_field_name = lead_data.get(sync_field)
                            if sync_field_name:
                                sync_field_name = int(sync_field_name)
                            if sync_field_name == sync_value:
                                pipedrive_id = lead_data.get('id')
                                record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                    lead_data,instance_id,field_model_name,dropdown_field_mapping_name,
                                    pipedrive_id,'lead', operation_type)
                                if operation_status == 'skip':
                                    continue
                                if record_data:
                                    record_data['pipedrive_id'] = pipedrive_id
                                    record_data['type'] = 'lead'
                                    record_data['odoo_hash'] = dynamic_fields_values_hash

                                    crm_record = self.env[odoo_model_name].search([('pipedrive_id', '=', pipedrive_id),
                                            ('type', '=', 'lead'), ('active', '=', True)],limit=1)
                                    if crm_record:
                                        partner_id_int = int(partner_id)
                                        crm_record.write({'partner_id': partner_id_int})
                                        crm_record.env.cr.commit()
                                        self.log_operation('lead', '', pipedrive_id, record_data, 'update', 'odoo', operation_type,
                                                           logger_name,record_id)
                                        self.pipedrive_update_odoo_id(pipedrive_id, crm_record,
                                                                      contact_model, api_token, 'lead', operation_type)
                                    else:
                                        # Extract user record using "owner_id"
                                        user_record = self.env['res.users'].get_lead_user_record(lead_data, "owner_id")
                                        if user_record:
                                            record_data['user_id'] = user_record.id
                                        crm_record = self.env[odoo_model_name].create(record_data)
                                        crm_record.env.cr.commit()
                                        if crm_record:
                                            partner_id_int = int(partner_id)
                                            crm_record.write({'partner_id': partner_id_int})
                                            crm_record.env.cr.commit()
                                            self.log_operation('lead', '', pipedrive_id, record_data, 'create', 'odoo', operation_type,
                                                               logger_name,
                                                               record_id)
                                            # Update Leads with partner ID
                                            self.pipedrive_update_odoo_id(pipedrive_id, crm_record,
                                                                          contact_model, api_token, 'lead', operation_type)
                            else:
                                continue
                        except Exception as e:
                            error_details = str(e)
                            error_type = 'Data Processing Error'
                            description = f'Error occurred while processing lead data for Pipedrive ID {pipedrive_id}.'
                            self.exception_log_error(error_details, 'lead', description, 'odoo', operation_type, pipedrive_id, error_type)

            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive leads data."
                self.http_log_error(error_details, 'lead', description, data_payload, response.text, 'odoo', operation_type, pipedrive_id,
                                    f"HTTP {response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related leads for {logger_name} ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'lead', description, 'odoo', operation_type, pipedrive_id, error_type)

    # ------------------------------ Company And Contact Related Deals ---------------------------- #
    def pipedrive_partner_related_deals(self, instance_id, pipedrive_model_name, related_field, odoo_model_name, record_id, api_token,
                                        contact_model, is_company, field_model_name, dropdown_field_mapping_name,
                                        logger_name, operation_type):
        """
            Description:
                Synchronizes deals related to a company and contact between Pipedrive and Odoo.

            Args:
                instance_id: The Pipedrive instance ID.
                pipedrive_model_name: The name of the Pipedrive model.
                odoo_model_name: The name of the Odoo model.
                record_id: The ID of the record in Pipedrive.
                api_token: Pipedrive API token.
                contact_model: The name of the contact model.
                is_company: Boolean indicating whether the record is a company.
                field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
                dropdown_field_mapping_name: The name of the field in `instance_id` containing dropdown mapping information.

            Returns:
                None
            """
        pipedrive_id = None
        try:
            deals_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?{related_field}={record_id}&api_token={api_token}"
            data_payload = {}
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            response = self.fetch_data(deals_endpoint, headers, data_payload, method="GET")
            partner_record = self.env['res.partner'].search(
                [('pipedrive_id', '=', record_id), ('is_company', '=', is_company), ('active', '=', True)], limit=1)
            partner_id = None
            if partner_record:
                partner_id = partner_record.id

            if response and response.status_code == 200:
                response_json = response.json()
                response_data = response_json.get('data')

                if response_data:  # Check if contacts_data is not None
                    # Iterate through the fetched contacts
                    for deal_data in response_data:
                        sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                        dropdown_field_mapping_name, 'deal', operation_type)
                        if not sync_value:
                            continue
                        sync_value = int(sync_value)
                        sync_field = self.get_field_from_mapper('opd.dealmapper', 'sync_to_odoo',
                                                                field_name='internal_name')
                        sync_field_name = self._get_pipedrive_custom_field_value(deal_data, sync_field)
                        if sync_field_name:
                            sync_field_name = int(sync_field_name)
                        if sync_field_name == sync_value:
                            pipedrive_id = deal_data.get('id')
                            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                deal_data,instance_id,field_model_name,dropdown_field_mapping_name,pipedrive_id,
                                'deal', operation_type)
                            if operation_status == 'skip':
                                continue
                            if record_data:
                                record_data['pipedrive_id'] = deal_data.get('id')
                                record_data['type'] = 'opportunity'
                                record_data['odoo_hash'] = dynamic_fields_values_hash

                                crm_record = self.env['crm.lead'].search(
                                    [('pipedrive_id', '=', pipedrive_id), ('type', '=', 'opportunity'),
                                     ('active', '=', True)], limit=1)

                                if crm_record:
                                    partner_id_int = int(partner_id)
                                    crm_record.write({'partner_id': partner_id_int})
                                    crm_record.env.cr.commit()
                                    self.log_operation('deal', '', pipedrive_id, record_data, 'update', 'odoo', operation_type, logger_name,
                                                       record_id)
                                    self.pipedrive_update_odoo_id(pipedrive_id, crm_record,
                                                                  contact_model, api_token, 'deal', operation_type)
                                else:
                                    # Extract user record using "owner_id"
                                    user_record = self.env['res.users'].get_user_record(deal_data, "owner_id")
                                    if user_record:
                                        record_data['user_id'] = user_record.id
                                    crm_record = self.env['crm.lead'].create(record_data)
                                    crm_record.env.cr.commit()
                                    if crm_record:
                                        partner_id_int = int(partner_id)
                                        crm_record.write({'partner_id': partner_id_int})
                                        crm_record.env.cr.commit()
                                        self.log_operation('deal', '', pipedrive_id, record_data, 'create', 'odoo', operation_type,
                                                           logger_name,
                                                           record_id)
                                        self.pipedrive_update_odoo_id(pipedrive_id, crm_record,
                                                                      contact_model, api_token, 'deal', operation_type)
                        else:
                            continue
                else:
                    return

            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to fetch Pipedrive opportunities data."
                self.http_log_error(error_details, 'deal', description, data_payload, response.text, 'odoo', operation_type, pipedrive_id,
                                    f"HTTP {response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related opportunities for {logger_name} ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'deal', description, 'odoo', operation_type, pipedrive_id, error_type)

        # --------------------------------- Contact Related Companies -------------------------------- #

    def pipedrive_contact_related_companies(self, instance_id, org_id, record_id, pipedrive_model_name, api_token,
        odoo_model_name,field_model_name, dropdown_field_mapping_name,logger_name, operation_type):

        """
           Description:
               Synchronizes contact-related companies between Pipedrive and Odoo.

           Args:
               instance_id: The Pipedrive instance ID.
               org_id: The ID of the organization in Pipedrive.
               record_id: The ID of the record in Pipedrive.
               pipedrive_model_name: The name of the Pipedrive model.
               api_token: Pipedrive API token.
               odoo_model_name: The name of the Odoo model.
               field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
               dropdown_field_mapping_name: The name of the field in `instance_id` containing dropdown mapping information.

           Returns:
               None
           """
        try:
            company = self.env[odoo_model_name].search(
                [('pipedrive_id', '=', org_id), ('is_company', '=', True), ('active', '=', True)], limit=1)
            contact = self.env[odoo_model_name].search(
                [('pipedrive_id', '=', record_id), ('is_company', '=', False), ('active', '=', True)], limit=1)

            if not org_id:
                contact.write({'parent_id': org_id})
                contact.env.cr.commit()
                return

            if company:
                partner_id = company.id
                partner_id_int = int(partner_id)
                contact.write({'parent_id': partner_id_int})
                contact.env.cr.commit()
                self.log_operation('company', '', org_id, {}, 'update', 'odoo', operation_type, logger_name, record_id)
            else:
                company_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{org_id}?api_token={api_token}"
                data_payload = {}
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.fetch_data(company_endpoint, headers, data_payload, method="GET")
                if response and response.status_code == 200:
                    response_json = response.json()
                    response_data = response_json.get('data')
                    if response_data:  # Check if company_data
                        try:
                            sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                            dropdown_field_mapping_name, 'company', operation_type)
                            if not sync_value:
                                return
                            sync_field = self.get_field_from_mapper('opd.companymapper', 'sync_to_odoo',
                                                                    field_name='internal_name')
                            sync_field_name = self._get_pipedrive_custom_field_value(response_data, sync_field)
                            if str(sync_field_name) == str(sync_value):
                                pipedrive_id = response_data.get('id')
                                record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                    response_data,instance_id,field_model_name,dropdown_field_mapping_name,
                                    pipedrive_id,'company', operation_type)
                                if operation_status == 'skip':
                                    return
                                if record_data:
                                    record_data['pipedrive_id'] = response_data.get('id')
                                    record_data['odoo_hash'] = dynamic_fields_values_hash
                                    record_data['is_company'] = True
                                    # Extract user record using "owner_id"
                                    user_record = self.env['res.users'].get_user_record(response_data, "owner_id")
                                    if user_record:
                                        record_data['user_id'] = user_record.id
                                    new_partner = self.env[odoo_model_name].create(record_data)
                                    new_partner.env.cr.commit()
                                    if new_partner:
                                        new_partner_id = new_partner.id
                                        partner_id_int = int(new_partner_id)
                                        contact.write({'parent_id': partner_id_int})
                                        contact.env.cr.commit()
                                        self.log_operation('company', '', pipedrive_id, record_data, 'create', 'odoo', operation_type,
                                                           logger_name,
                                                           record_id)
                                        self.pipedrive_update_odoo_id(org_id, new_partner,
                                                                      pipedrive_model_name, api_token, 'company', operation_type)
                            else:
                                return

                        except Exception as e:
                            self.exception_log_error(str(e), 'company', 'Data Processing Error', 'odoo', operation_type, org_id,
                                                     'Exception Error')

                else:
                    self.http_log_error(f"{response.status_code} - {response.reason}", 'company',
                                        f"Failed to fetch Pipedrive company data.", data_payload, response.text, 'odoo', operation_type, org_id,
                                        f"HTTP {response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related company for Contact ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'company', description, 'odoo', operation_type, org_id, error_type)

    # --------------------- Fetch CRM Data From Pipedrive (v1 + v2 Unified) ----------------- #
    @api.model
    def fetch_crm_data_from_pipedrive(self, instance_id, pipedrive_model_name, odoo_model_name,
                                      field_model_name, field_mapper_model, last_sync_date_field,
                                      calls_field, tasks_field, emails_field, meetings_field, notes_field,
                                      type, object, dropdown_field_mapping_name, crm_type, logger_name,
                                      operation_type):

        try:
            # ---------------------- Sync Date Setup ---------------------- #
            last_sync_date, current_utc_time = self.last_sync_date_common(last_sync_date_field)
            updated_since = last_sync_date.strftime('%Y-%m-%dT%H:%M:%SZ') if last_sync_date else None
            filter_date_value = last_sync_date.strftime('%Y-%m-%d') if last_sync_date else None

            record_last_id = instance_id.pipedrive_deal_last_id if crm_type == 'opportunity' else instance_id.pipedrive_lead_last_id
            api_token = instance_id.api_token
            limit = instance_id.pagination_size or 100
            cursor, offset = None, 0

            # Determine version logic
            if crm_type == 'opportunity':
                api_version = 'v2'
                pagination_mode = 'cursor'
                if not self.get_validated_api_base_url(instance_id, logger_name, operation_type):
                    return
            else:
                api_version = 'v1'
                pagination_mode = 'offset'
            more_items = None
            is_field_mapping = self.has_field_mappings(field_model_name, instance_id, logger_name, operation_type)
            if not is_field_mapping:
                return

            # ---------------------- Loop ---------------------- #
            while True:
                sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                dropdown_field_mapping_name, logger_name,
                                                                operation_type)
                update_time_value = self.get_update_time_field(field_mapper_model, 'update_time')
                last_field_id = self.get_update_time_field(field_mapper_model, 'id')

                # Create filter_id only if last_sync_date exists
                if last_sync_date and sync_value:
                    if crm_type == 'opportunity':
                        filter_id = self.env['opd.mapper.mixin'].fetch_filter_id(
                            api_token, filter_date_value, sync_value, update_time_value,
                            sync_field_id, type, object, logger_name, last_field_id,
                            record_last_id, operation_type
                        )
                    else:
                        filter_id = self.env['opd.mapper.mixin'].fetch_related_filter_id(
                            api_token, filter_date_value, sync_value, update_time_value,
                            sync_field_id, type, object, logger_name, operation_type
                        )
                else:
                    break

                # ---------------------- Build Endpoint ---------------------- #
                if api_version == 'v2':
                    endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?filter_id={filter_id}&limit={limit}&updated_since={updated_since}&sort_by=id&sort_direction=asc&api_token={api_token}"
                    if cursor:
                        endpoint += f"&cursor={cursor}"
                else:
                    endpoint = f'{self.__API_BASE_URL}{pipedrive_model_name}?sort=id ASC&archived_status=not_archived&filter_id={filter_id}&start={offset}&limit={limit}&api_token={api_token}'

                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, {}, method="GET")
                if response.status_code != 200:
                    self.http_log_error(f"No record found: {response.text}", logger_name, "Error fetching CRM data", {},
                                        response.text, 'odoo', operation_type, '', f"HTTP {response.status_code}")
                    break

                response_json = response.json()
                crm_records = response_json.get('data', [])

                # Handle pagination
                if pagination_mode == 'cursor':
                    additional_data = response_json.get('additional_data', {})
                    cursor = additional_data.get('next_cursor')
                else:
                    offset += limit
                    pagination = response_json.get('additional_data', {}).get('pagination', {})
                    more_items = pagination.get('more_items_in_collection', False)

                # ---------------------- Process Records ---------------------- #
                for record in crm_records:
                    record_id = record.get('id')
                    record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                        record, instance_id, field_model_name, dropdown_field_mapping_name, record_id, logger_name,
                        operation_type
                    )

                    if operation_status == 'skip' or not record_data:
                        continue

                    record_data['pipedrive_id'] = record_id
                    record_data['type'] = crm_type
                    record_data['odoo_hash'] = dynamic_fields_values_hash

                    user_record = self.get_user_record(record, crm_type)
                    if user_record:
                        record_data['user_id'] = user_record.id

                    odoo_record = self.env[odoo_model_name].search([
                        ('pipedrive_id', '=', record_id),
                        ('type', '=', crm_type),
                        ('active', '=', True)
                    ], limit=1)

                    if not odoo_record:
                        self.create_crm_odoo_record(api_token, odoo_model_name, record_data, record_id, logger_name,
                                                    pipedrive_model_name, crm_type, instance_id, calls_field,
                                                    tasks_field,
                                                    emails_field, meetings_field, notes_field, record, operation_type,
                                                    check_hash=True)
                    elif odoo_record.odoo_hash != dynamic_fields_values_hash:
                        self.update_crm_odoo_record(api_token, odoo_record, record_data, record_id, logger_name,
                                                    field_model_name, dropdown_field_mapping_name, pipedrive_model_name,
                                                    crm_type, instance_id, calls_field, tasks_field, emails_field,
                                                    meetings_field, notes_field, odoo_model_name, record,
                                                    operation_type, check_hash=True)

                # Update last_id
                if crm_records:
                    record_last_id = crm_records[-1].get('id')
                    if crm_type == 'opportunity':
                        instance_id.write({'pipedrive_deal_last_id': record_last_id})
                    else:
                        instance_id.write({'pipedrive_lead_last_id': record_last_id})
                    instance_id.env.cr.commit()

                # Break conditions
                if pagination_mode == 'cursor' and not cursor:
                    break
                if pagination_mode == 'offset' and not more_items:
                    break

            # ---------------------- Final Update ---------------------- #
            if crm_type == 'opportunity':
                instance_id.write({'pipedrive_deal_last_sync_date': current_utc_time, 'pipedrive_deal_last_id': 0})
            else:
                instance_id.write({'pipedrive_lead_last_sync_date': current_utc_time, 'pipedrive_lead_last_id': 0})

            self.scheduler_run_successfully_log(logger_name, operation_type, 'odoo')

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} Create/Update in Odoo.'
            self.exception_log_error(error_details, logger_name, description, 'odoo', operation_type, '', error_type)

    # ------------------------------------- Create Lead Or Deal in Odoo -------------------------------- #

    def create_crm_odoo_record(self, api_token, odoo_model_name, record_data, record_id, logger_name, pipedrive_model_name, crm_type, instance_id, calls_field,
                               tasks_field, emails_field, meetings_field, notes_field, record, operation_type, check_hash=True):
        """
           Create a new lead or deal record in Odoo.

           Args:
               odoo_model_name (str): The name of the Odoo model.
               record_data (dict): The data for the new record.
               record_id (int): The ID of the record in Pipedrive.
               logger_name (str): The name of the logger.
               field_model_name (str): The name of the field model.
               dropdown_field_mapping_name (str): The name of the dropdown field mapping.
               pipedrive_model_name (str): The name of the Pipedrive model.
               crm_type (str): The type of CRM record (lead or opportunity).https://apps.odoo.com/apps/modules/19.0/sh_odoo_fabric_connector
               instance_id (int): The instance ID of Pipedrive.
               calls_field (str): The field name for calls.
               tasks_field (str): The field name for tasks.
               emails_field (str): The field name for emails.https://apps.odoo.com/apps/modules/19.0/sh_odoo_fabric_connector
               meetings_field (str): The field name for meetings.
               notes_field (str): The field name for notes.
               record (dict): The record data.
               check_hash(Bool): Check Odoo Hash based on Check hash True or False
           Returns:
               str: 'create' on successful creation.
           """
        odoo_record = self.env[odoo_model_name].create(record_data)
        odoo_record.env.cr.commit()
        self.log_operation(logger_name, '', record_id, record_data, 'create', 'odoo', operation_type, None, None)
        self.pipedrive_update_odoo_id(record_id, odoo_record, pipedrive_model_name,
                                      api_token, logger_name, operation_type)
        self.process_crm_related_contacts_and_companies(instance_id, record, record_id, crm_type,
                                                        api_token, logger_name, operation_type)
        self.fetch_crm_related_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
                                        emails_field, meetings_field, notes_field, pipedrive_model_name, record_id, crm_type,
                                        api_token, logger_name, operation_type, check_hash)


        return 'create'

    # --------------------------------- Update Lead Or Deal -------------------- #

    def update_crm_odoo_record(self, api_token, odoo_record, record_data, record_id, logger_name, field_model_name,
                               dropdown_field_mapping_name, pipedrive_model_name, crm_type, instance_id, calls_field,
                               tasks_field, emails_field, meetings_field, notes_field, odoo_model_name, record, operation_type,
                               check_hash=True):
        """
            Update an existing lead or deal record in Odoo.

            Args:
                odoo_record (record): The existing Odoo record to update.
                record_data (dict): The data to update the record with.
                record_id (str,int): The ID of the record in Pipedrive.
                logger_name (str): The name of the logger.
                field_model_name (str): The name of the field model.
                dropdown_field_mapping_name (str): The name of the dropdown field mapping.
                pipedrive_model_name (str): The name of the Pipedrive model.
                crm_type (str): The type of CRM record (lead or opportunity).
                instance_id (int): The instance ID of Pipedrive.
                calls_field (str): The field name for calls.
                tasks_field (str): The field name for tasks.
                emails_field (str): The field name for emails.
                meetings_field (str): The field name for meetings.
                notes_field (str): The field name for notes.
                odoo_model_name (str): The name of the Odoo model.
                record (dict): The record data.
                check_hash(Bool): Check Odoo Hash based on Check hash True or False
            Returns:
                str: 'update' on successful update.
            """
        partner_user_id = odoo_record.user_id.id
        odoo_user = self.get_odoo_user_from_pipedrive_record(record)
        pipedrive_user_id = odoo_user.id if odoo_user else None
        if partner_user_id == pipedrive_user_id:
            record_data.pop('user_id', None)
        odoo_record.write(record_data)
        odoo_record.env.cr.commit()
        self.log_operation(logger_name, '', record_id, record_data, 'update', 'odoo', operation_type, None, None)
        self.pipedrive_update_odoo_id(record_id, odoo_record, pipedrive_model_name,api_token, logger_name, operation_type)
        self.process_crm_related_contacts_and_companies(instance_id, record, record_id, crm_type,
                                                        api_token, logger_name, operation_type)
        self.fetch_crm_related_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
                                        emails_field,meetings_field, notes_field, pipedrive_model_name, record_id,
                                        crm_type,api_token, logger_name, operation_type,check_hash)

        return 'update'

    # ----------------------------------- GET Lead And Deal User ID --------------- #

    def get_user_record(self, record, crm_type):
        """
            Get the user record for a lead or deal.

            Args:
                record (dict): The CRM record data.
                crm_type (str): The type of CRM record (lead or opportunity).

            Returns:
                record: The user record.
            """
        return self.get_odoo_user_from_pipedrive_record(record, 'owner_id')

    # --------------------------- CRM Related Companies And Contacts ----------------------- #
    def process_crm_related_contacts_and_companies(self, instance_id, record, record_id, crm_type,
                                                   api_token, logger_name, operation_type):
        """
            Process related contacts and companies for a CRM record.

            Args:
                instance_id (int): The instance ID of Pipedrive.
                record (dict): The CRM record data.
                record_id (int): The ID of the record in Pipedrive.
                pipedrive_model_name (str): The name of the Pipedrive model.
                crm_type (str): The type of CRM record (lead or opportunity).
                api_token (str): The API token for Pipedrive.
                logger_name (str): The name of the logger.

            Returns:
                None
        """
        lead_email, odoo_id = None, None
        if crm_type == 'lead':
            lead_organization_id = record.get('organization_id')
            lead_person_id = record.get('person_id')

            if lead_person_id:
                contact_details = self.fetch_contact_details(instance_id, lead_person_id, api_token, 'lead', operation_type)

                if contact_details:
                    odoo_id = contact_details['odoo_id']
                    lead_email = contact_details['lead_person_email']

            if instance_id.pipedrive_lead_related_companies and lead_organization_id:
                self.pipedrive_crm_related_companies(instance_id, lead_organization_id, record_id,
                'organizations',api_token, 'res.partner',
                'pipedriveinstance.companies.lines','pipedrive_company_dropdown_mapping',
                crm_type, logger_name, operation_type)

            if instance_id.pipedrive_lead_related_contacts and not lead_organization_id and (lead_person_id or lead_email):
                self.pipedrive_crm_related_contacts(instance_id, odoo_id, lead_person_id, lead_email, record_id,
                     'persons',api_token, 'res.partner',
                     'pipedriveinstance.contacts.lines','pipedrive_contacts_dropdown_mapping',
                     crm_type, logger_name, operation_type)

        elif crm_type == 'opportunity':
            deal_organization_id = record['org_id'] if record['org_id'] is not None else None
            deal_contact_id = record['person_id'] if record['person_id'] is not None else None
            if instance_id.pipedrive_deal_related_companies and deal_organization_id and not deal_contact_id:
                self.pipedrive_crm_related_companies(instance_id, deal_organization_id, record_id,
                                                     'organizations',api_token,
                                                     'res.partner','pipedriveinstance.companies.lines',
                                                     'pipedrive_company_dropdown_mapping',
                                                     crm_type, logger_name, operation_type)

            if deal_contact_id and instance_id.pipedrive_deal_related_contacts:
                contact_details = self.fetch_contact_details(instance_id, deal_contact_id, api_token, 'deal', operation_type)
                if contact_details:
                    odoo_id = contact_details['odoo_id']
                    deal_contact_email = contact_details['lead_person_email']
                    self.pipedrive_crm_related_contacts(instance_id, odoo_id, deal_contact_id, deal_contact_email,
                    record_id,'persons',api_token, 'res.partner',
                    'pipedriveinstance.contacts.lines','pipedrive_contacts_dropdown_mapping',
                    crm_type, logger_name, operation_type)

    # --------------------------- Fetch contact details from Pipedrive ----------------------- #

    def fetch_contact_details(self, instance_id, person_id, api_token, logger_name, operation_type):
        """
        Fetch contact details from Pipedrive.

        Args:
            person_id (int): The ID of the person in Pipedrive.
            api_token (str): The API token for Pipedrive.

        Returns:
            dict: A dictionary containing 'odoo_id' and 'lead_person_email' if the request is successful.
                  Returns None if the request fails.
        """
        contact_endpoint = f"{instance_id.api_base_url}/persons/{person_id}?api_token={api_token}"
        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
        payload_rec = {}
        response = self.env['opd.mapper.mixin'].fetch_data(contact_endpoint, headers, payload_rec, method="GET")
        if response.status_code == 200:
            response_json = response.json()
            person_record = response_json.get('data', [])
            lead_person_email = person_record.get('primary_email')
            sync_field = self.env['opd.mapper.mixin'].get_field_from_mapper('opd.contactmapper', 'odoo_id',
                                                                            field_name='internal_name')
            odoo_id = self._get_pipedrive_custom_field_value(person_record, sync_field)
            return {
                'odoo_id': odoo_id,
                'lead_person_email': lead_person_email
            }
        else:
            error_details = f"{response.status_code} - {response.reason}"
            description = f"Failed to fetch pipedrive {logger_name} email."
            self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, payload_rec,
            response.text, operation_type,'odoo', person_id, f"HTTP {response.status_code}")
            return None

    # --------------------------------- Fetch Crm Related Activity From Pipedrive --------------------------- #
    def fetch_crm_related_activity(self, instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
           emails_field,meetings_field, notes_field, pipedrive_model_name, record_id, crm_type, api_token,
           logger_name, operation_type, check_hash=True):
        if crm_type == 'lead':
            self.fetch_activity_for_leads(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field,
                emails_field,meetings_field, notes_field, api_token, 'activities',
                record_id,'activity', 'activity', logger_name, operation_type, check_hash)
        else:
            self.fetch_activity(instance_id, odoo_record, odoo_model_name, calls_field, tasks_field, emails_field,
            meetings_field, notes_field, pipedrive_model_name, record_id, api_token, logger_name, operation_type,
            check_hash)

    # ----------------------- Fetch Crm Related Companies -------------------------- #

    def pipedrive_crm_related_companies(self, instance_id, lead_organization_id, record_id, pipedrive_model_name,
        api_token,odoo_model_name,field_model_name, dropdown_field_mapping_name,crm_type, logger_name, operation_type):

        """
            Description:
                Synchronizes lead-related companies between Pipedrive and Odoo.

            Args:
                instance_id: The Pipedrive instance ID.
                lead_organization_id: The ID of the lead organization in Pipedrive.
                record_id: The ID of the record in Pipedrive.
                pipedrive_model_name: The name of the Pipedrive model.
                api_token: Pipedrive API token.
                odoo_model_name: The name of the Odoo model.
                field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
                dropdown_field_mapping_name: The name of the field in `instance_id` containing dropdown mapping information.

            Returns:
                None
            """
        try:
            partner = self.env[odoo_model_name].search(
                [('pipedrive_id', '=', lead_organization_id), ('is_company', '=', True), ('active', '=', True)],limit=1)
            crm_record = self.env['crm.lead'].search(
                [('pipedrive_id', '=', record_id), ('type', '=', crm_type), ('active', '=', True)], limit=1)
            if partner:
                partner_id_int = int(partner.id)
                crm_record.write({'partner_id': partner_id_int})
                crm_record.env.cr.commit()
                self.log_operation('company', '', lead_organization_id, None, 'update', 'odoo', operation_type, logger_name, record_id)
            else:
                company_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{lead_organization_id}?api_token={api_token}"
                data_payload = {}
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.fetch_data(company_endpoint, headers, data_payload, method="GET")

                if response and response.status_code == 200:
                    response_json = response.json()
                    response_data = response_json.get('data')

                    if response_data:  # Check if company_data is not None
                        sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                        dropdown_field_mapping_name, 'company', operation_type)
                        if not sync_value:
                            return
                        sync_field = self.get_field_from_mapper('opd.companymapper', 'sync_to_odoo',
                                                                field_name='internal_name')
                        sync_field_name = self._get_pipedrive_custom_field_value(response_data, sync_field)

                        if str(sync_field_name) == str(sync_value):
                            pipedrive_id = response_data.get('id')
                            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                response_data,instance_id,field_model_name,dropdown_field_mapping_name,pipedrive_id,
                                'company', operation_type)
                            if operation_status == 'skip':
                                return
                            if record_data:
                                record_data['pipedrive_id'] = pipedrive_id
                                record_data['is_company'] = True
                                record_data['odoo_hash'] = dynamic_fields_values_hash

                                # Extract user record using "owner_id"
                                user_record = self.env['res.users'].get_user_record(response_data, "owner_id")
                                if user_record:
                                    record_data['user_id'] = user_record.id
                                new_partner = self.env[odoo_model_name].create(record_data)
                                new_partner.env.cr.commit()
                                self.pipedrive_update_odoo_id(lead_organization_id, new_partner,
                                                              pipedrive_model_name, api_token, 'company', operation_type)
                                if new_partner:
                                    new_partner_id = new_partner.id
                                    partner_id_int = int(new_partner_id)
                                    crm_record.write({'partner_id': partner_id_int})
                                    crm_record.env.cr.commit()
                                    self.log_operation('company', '', pipedrive_id, record_data, 'create', 'odoo', operation_type,
                                                       logger_name,record_id)
                        else:
                            return
                else:
                    self.http_log_error(f"{response.status_code} - {response.reason}", 'company',
                                        f"Failed to fetch Pipedrive Contact data.", data_payload, response.text,
                                        'odoo', operation_type, lead_organization_id, f"HTTP {response.status_code}")

        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related company for {logger_name} ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'company', description, 'odoo', operation_type, lead_organization_id, error_type)

    # --------------------------------- Fetch Crm Related Contacts -------------------------------- #

    def pipedrive_crm_related_contacts(self, instance_id, odoo_id, deal_contact_id, deal_contact_email, record_id,
                                       pipedrive_model_name,api_token,odoo_model_name,field_model_name,
                                       dropdown_field_mapping_name,crm_type, logger_name, operation_type):

        """
           Description:
               Synchronizes deal-related contacts between Pipedrive and Odoo.

           Args:
               instance_id: The Pipedrive instance ID.
               deal_contact_id: The ID of the organization in Pipedrive.
               record_id: The ID of the record in Pipedrive.
               pipedrive_model_name: The name of the Pipedrive model.
               api_token: Pipedrive API token.
               odoo_model_name: The name of the Odoo model.
               field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
               dropdown_field_mapping_name: The name of the field in `instance_id` containing dropdown mapping information.

           Returns:
               None
           """
        try:

            # Search for existing partner by email or ID
            partner, email_exists_with_pipedrive_id = self.search_partner(deal_contact_email, odoo_id, False)
            crm_record = self.env['crm.lead'].search(
                [('pipedrive_id', '=', record_id), ('type', '=', crm_type), ('active', '=', True)], limit=1)
            if email_exists_with_pipedrive_id:
                description = f'{logger_name.capitalize()} related contact email ID {deal_contact_email} is already associated with another contact with a Pipedrive ID. Please use a different email ID.'
                operation = f'{logger_name} related contact send pipedrive to odoo'
                self.log_operation_warning(logger_name, description, operation, 'odoo', partner, operation_type, record_id)
                return

            if partner and not email_exists_with_pipedrive_id:
                partner_id_int = int(partner.id)
                crm_record.write({'partner_id': partner_id_int})
                crm_record.env.cr.commit()
                self.log_operation('contact', '', deal_contact_id, None, 'update', 'odoo', operation_type, logger_name, record_id)
            else:
                contact_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{deal_contact_id}?api_token={api_token}"
                data_payload = {}
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                response = self.fetch_data(contact_endpoint, headers, data_payload, method="GET")
                if response and response.status_code == 200:
                    response_json = response.json()
                    response_data = response_json.get('data')
                    if response_data:  # Check if company_data is not None
                        sync_value, sync_field_id = self.get_sync_value(instance_id, field_model_name,
                                                                        dropdown_field_mapping_name, 'contact', operation_type)
                        if not sync_value:
                            return
                        sync_field = self.get_field_from_mapper('opd.contactmapper', 'sync_to_odoo',
                                                                field_name='internal_name')
                        sync_field_name = self._get_pipedrive_custom_field_value(response_data, sync_field)
                        if str(sync_field_name) == str(sync_value):
                            pipedrive_id = response_data.get('id')
                            record_data, odoo_id_value, dynamic_fields_values_hash, operation_status = self.pipedrive_to_odoo_map_fields(
                                response_data,instance_id,field_model_name,dropdown_field_mapping_name,pipedrive_id,
                                'contact', operation_type)
                            if operation_status == 'skip':
                                return
                            if record_data:
                                record_data['pipedrive_id'] = response_data.get('id')
                                record_data['is_company'] = False
                                record_data['odoo_hash'] = dynamic_fields_values_hash

                                # Extract user record using "owner_id"
                                user_record = self.env['res.users'].get_user_record(response_data, "owner_id")
                                if user_record:
                                    record_data['user_id'] = user_record.id
                                new_partner = self.env[odoo_model_name].create(record_data)
                                new_partner.env.cr.commit()
                                self.pipedrive_update_odoo_id(pipedrive_id, new_partner,
                                                              pipedrive_model_name, api_token, 'contact', operation_type)
                                if new_partner:
                                    new_partner_id = new_partner.id
                                    partner_id_int = int(new_partner_id)
                                    crm_record.write({'partner_id': partner_id_int})
                                    crm_record.env.cr.commit()
                                    self.log_operation('contact', '', pipedrive_id, record_data, 'create', 'odoo', operation_type,
                                                       logger_name, record_id)
                        else:
                            return
                else:
                    self.http_log_error(f"{response.status_code} - {response.reason}", 'contact',
                                        f"Failed to fetch Pipedrive Contact data.", data_payload, response.text,
                                        'odoo', operation_type, deal_contact_id, f"HTTP {response.status_code}")
        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related Contact for {logger} ID {record_id} from Pipedrive.'
            self.exception_log_error(error_details, 'contact', description, 'odoo', operation_type, deal_contact_id, error_type)

    # ---------------------------- Fetch All Activities and Notes From Pipedrive ------------------------------ #

    def fetch_all_pipedrive_activities(self, instance_id, last_sync_date_field, activity_mapper_model, ac_type,
                                       ac_object, operation_type):
        """
        Fetch all activities and notes from Pipedrive and create/update them in Odoo.

        This function fetches activities and notes from Pipedrive using the provided API token, and synchronizes them with
        the corresponding records in Odoo. It processes each activity and note based on the last sync date and handles
        pagination to fetch data in batches.

        Args:
            instance_id (recordset): The Pipedrive instance configuration.
            last_sync_date_field (datetime): The date of the last synchronization.
            activity_field_id (str): The field ID for activities.
            ac_type (str): The type of the activity.
            ac_object (str): The object type of the activity (e.g., 'activity').

        Raises:
            UserError: If pagination size is less than or equal to zero.
            Exception: For any other errors that occur during the process, logs the error details.
        """
        try:
            api_token = instance_id.api_token if 'api_token' in instance_id else None
            last_sync_date, current_utc_time = self.last_sync_date_common(last_sync_date_field)

            # Format it to the desired format
            formatted_time = last_sync_date.strftime('%Y-%m-%d %H:%M:%S')
            # Convert the formatted string back into a datetime object
            final_datetime = datetime.strptime(formatted_time, '%Y-%m-%d %H:%M:%S')
            start = 0
            pagination_size = instance_id.pagination_size
            if pagination_size <= 0:
                raise UserError(_('Pagination size should be greater than zero.'))
            limit = pagination_size
            activity_field_id = self.get_update_time_field(activity_mapper_model, 'update_time')
            while True:
                if last_sync_date:
                    activity_filter_id = self.fetch_activity_filter_id(api_token, last_sync_date.strftime('%Y-%m-%d'),
                                                                       activity_field_id,
                                                                       ac_type, ac_object, 'activity', '>=', operation_type)
                else:
                    break
                endpoint = f'{self.__API_BASE_URL}activities?user_id=0&filter_id={activity_filter_id}&start={start}&limit={limit}&api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                payload_rec = {}
                response = self.fetch_data(endpoint, headers, payload_rec, method="GET")
                if response.status_code == 200:
                    response_json = response.json()
                    records = response_json.get('data', [])
                    if not records:
                        break

                    for record in records:
                        update_time = record.get('update_time')
                        pipedrive_activity_update_time = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                        if pipedrive_activity_update_time > final_datetime:
                            self.create_odoo_activity(record, operation_type)

                    if len(records) < limit:
                        break
                    start += pagination_size
                else:
                    error_details = f"{response.status_code} - {response.reason}"
                    description = f"Failed to fetch Pipedrive activity records."
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'activity', description, payload_rec,
                                                                'odoo', response.text, operation_type, '', f"HTTP {response.status_code}")
                    break

            # -------------------------- Fetch Pipedrive Notes And Send To Odoo --------------------- #

            start = 0
            notes_last_sync_date = last_sync_date.strftime('%Y-%m-%d')
            while True:
                note_endpoint = f'{self.__API_BASE_URL}notes/?start_date={notes_last_sync_date}&start={start}&limit={limit}&api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                payload_rec = {}
                note_response = self.fetch_data(note_endpoint, headers, payload_rec, method="GET")

                if note_response.status_code == 200:
                    note_records = note_response.json().get('data', [])
                    if not note_records:
                        break

                    for record in note_records:
                        update_time = record.get('update_time')
                        pipedrive_note_update_time = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                        if pipedrive_note_update_time > final_datetime:
                            self.create_odoo_note(record, operation_type)

                    if len(note_records) < limit:
                        break
                    start += pagination_size
                else:
                    error_details = f"{note_response.status_code} - {note_response.reason}"
                    description = f"Failed to fetch Pipedrive note records"
                    self.env['opd.mapper.mixin'].http_log_error(error_details, 'note', description, payload_rec,
                                                                note_response.text, 'odoo', operation_type, '',
                                                                f"HTTP {note_response.status_code}")
                    break

            if last_sync_date:
                instance_id.write({'pipedrive_activity_last_sync_date': current_utc_time})
                self.env['opd.mapper.mixin'].scheduler_run_successfully_log('activities', operation_type,
                                                                            'odoo')
        except Exception as e:
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching Pipedrive activities and notes'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'activity', description, 'odoo', operation_type, '', error_type)

    # ------------------------ Search Odoo Records with activity ------------------------ #

    def search_odoo_records(self, data):
        """
        Search for corresponding records in Odoo based on Pipedrive IDs.
        """
        odoo_records = []
        org_id = data.get('org_id')
        person_id = data.get('person_id')
        deal_id = data.get('deal_id')
        lead_id = data.get('lead_id')

        if org_id:
            odoo_records += self.env['res.partner'].search(
                [('pipedrive_id', '=', org_id), ('is_company', '=', True), ('sync_to_pipedrive', '=', 'yes'),
                 ('active', '=', True)], limit=1)
        if person_id:
            odoo_records += self.env['res.partner'].search(
                [('pipedrive_id', '=', person_id), ('is_company', '=', False), ('sync_to_pipedrive', '=', 'yes'),
                 ('active', '=', True)], limit=1)
        if deal_id:
            odoo_records += self.env['crm.lead'].search(
                [('pipedrive_id', '=', deal_id), ('type', '=', 'opportunity'), ('sync_to_pipedrive', '=', 'yes'),
                 ('active', '=', True)], limit=1)
        if lead_id:
            odoo_records += self.env['crm.lead'].search(
                [('pipedrive_id', '=', lead_id), ('type', '=', 'lead'), ('sync_to_pipedrive', '=', 'yes'),
                 ('active', '=', True)], limit=1)

        return odoo_records

    # ------------------------- Create Activities in Odoo ------------------------ #

    def create_odoo_activity(self, activity, operation_type):
        """
           Create or update an activity in Odoo based on Pipedrive activity data.

           This function maps the Pipedrive activity type to the corresponding Odoo activity type and either creates or updates
           the activity in Odoo. It ensures that activities are linked to the correct records in Odoo.

           Args:
               instance_id (recordset): The Pipedrive instance configuration.
               activity (dict): The Pipedrive activity data.

           Raises:
               Exception: For any errors that occur during the process, logs the error details.
           """

        # Extract relevant data from the Pipedrive activity
        try:
            activity_type = activity.get('type')
            due_date = activity.get('due_date')
            activity_id = activity.get('id')
            activity_user_id = activity.get('user_id')
            pipedrive_user = self.env['res.users'].search(
                [('pipedrive_id', '=', activity_user_id), ('share', '=', False), ('active', '=', True)], limit=1)
            pipedrive_user_id = pipedrive_user.id
            odoo_user_id = None

            note = activity.get('note') if activity.get('note') else None
            if activity.get('note'):
                # Parse the HTML string using BeautifulSoup
                note_str = BeautifulSoup(note, 'html.parser')
                # Extract the text content from the HTML using the get_text() method
                note_text = note_str.get_text()
            else:
                note_text = ''

            odoo_user = self.env['res.users'].search(
                [('pipedrive_id', '=', activity_user_id), ('share', '=', False), ('active', '=', True)], limit=1)

            if odoo_user:
                odoo_user_id = odoo_user.id
            else:
                _logger.info(f"User ID {activity_user_id} does not exist in res_users table.")

            # Map Pipedrive activity type to Odoo activity type
            odoo_activity_type_id = None
            if activity_type == 'call':
                odoo_activity_type_id = 2
            elif activity_type == 'email':
                odoo_activity_type_id = 1
            elif activity_type == 'meeting':
                odoo_activity_type_id = 3
            elif activity_type == 'task':
                odoo_activity_type_id = 4

            # Search for corresponding records in Odoo based on Pipedrive IDs
            odoo_records = self.search_odoo_records(activity)

            for odoo_record in odoo_records:
                # Check if the activity already exists
                odoo_record_id = self.get_record_id(odoo_record)
                existing_activity = self.env['mail.activity'].search([
                    ('pipedrive_activity_id', '=', activity_id), ('res_id', '=', odoo_record_id), ('active', '=', True)
                ], limit=1)

                if existing_activity:
                    # Update existing activity

                    odoo_user_id = existing_activity.user_id.id
                    update_vals = {
                        'date_deadline': due_date,
                        'summary': activity.get('subject'),
                        'note': note_text,
                        'user_id': odoo_user_id,
                    }
                    if odoo_user_id == pipedrive_user_id:
                        update_vals.pop('user_id', None)
                    else:
                        update_vals = update_vals

                    existing_activity.write(update_vals)
                    existing_activity.env.cr.commit()
                    self.log_operation('activity', '', activity_id, update_vals, 'update',
                                                               'odoo', operation_type, parent_name=None,
                                                               parent_id=None)
                else:
                    # Create new activity
                    res_model_id = self.env['ir.model']._get(odoo_record._name).id
                    active = not activity.get('done', False)

                    if not odoo_record.id:
                        return

                    vals = {
                        'activity_type_id': odoo_activity_type_id,
                        'res_id': odoo_record_id,
                        'user_id': odoo_user_id,
                        'date_deadline': due_date,
                        'res_model_id': res_model_id,
                        'summary': activity.get('subject'),
                        'note': note_text,
                        'pipedrive_activity_id': activity_id  # Save Pipedrive activity ID in Odoo
                    }
                    new_activity = self.env['mail.activity'].create(vals)
                    if not active:  # ← You can control this with a condition or sync flag
                        new_activity.action_done()
                    else:
                        new_activity.env.cr.commit()
                    self.env['opd.mapper.mixin'].log_operation('activity', '', activity_id, vals, 'create',
                                                               'odoo', operation_type, parent_name=None,
                                                               parent_id=None)

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching pipedrive activities and notes'
            self.env['opd.mapper.mixin'].exception_log_error(error_details, 'activity', description, 'odoo', operation_type, '', error_type)

    # ----------------------------- Create Note in Odoo ----------------------------- #

    def create_odoo_note(self, note, operation_type):
        """
            Create or update a note in Odoo based on Pipedrive note data.

            This function synchronizes notes from Pipedrive with the corresponding records in Odoo, ensuring that notes are
            properly linked to their respective records.

            Args:
                instance_id (recordset): The Pipedrive instance configuration.
                note (dict): The Pipedrive note data.

            Raises:
                Exception: For any errors that occur during the process, logs the error details.
        """
        # Extract relevant data from the Pipedrive note
        content = note.get('content')
        note_id = note.get('id')

        # Search for corresponding records in Odoo based on Pipedrive IDs
        odoo_records = self.search_odoo_records(note)

        for odoo_record in odoo_records:
            # Check if the note already exists
            odoo_record_id = self.get_record_id(odoo_record)
            model_name = odoo_record._name
            existing_note = self.env['mail.message'].search([
                ('pipedrive_notes_id', '=', note_id), ('res_id', '=', odoo_record_id)], limit=1)

            if existing_note:
                update_vals = {
                    'body': content,
                }
                existing_note.write(update_vals)
                existing_note.env.cr.commit()
                self.env['opd.mapper.mixin'].log_operation('note', '', note_id, update_vals, 'update',
                                                           'odoo', operation_type, parent_name=None,
                                                           parent_id=None)
            else:
                vals = {
                    'res_id': odoo_record_id,
                    'body': content,
                    'message_type': 'comment',
                    'model': model_name,  # Replace 'your.model.name' with the appropriate Odoo model name
                    'pipedrive_notes_id': note_id
                }
                new_note = self.env['mail.message'].create(vals)
                new_note.env.cr.commit()
                self.env['opd.mapper.mixin'].log_operation('note', '', note_id, vals, 'create',
                                                           'odoo', operation_type, parent_name=None,
                                                           parent_id=None)

    # ----------------------------------- Update or Create Pipedrive Record -------------------- #
    def update_or_create_pipedrive_record(self, record_data, endpoint, headers, logger_name, operation_type, method="POST"):
        payload = json.dumps(record_data)
        response = None
        try:
            response = requests.request(method, endpoint, headers=headers, data=payload)
            response.raise_for_status()  # Raise an error for bad status codes
        except requests.exceptions.RequestException as e:
            error_details = str(e)
            status_code = response.status_code if response is not None else 'N/A'
            description = _('Failed to %(method)s Pipedrive %(entity)s record.') % {
                'method': method.upper(),
                'entity': logger_name,
            }
            self.http_log_error(
                error_details, logger_name, description, record_data, error_details,
                'pipedrive', operation_type, '', f'HTTP {status_code}'
            )
            return None, response.status_code if response is not None else None

        try:
            return response.json().get('data', {}), response.status_code
        except ValueError as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Failed to parse JSON response: Error occurred while {logger_name} create/update in pipedrive.'
            self.exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, '', error_type)
            return None, None

    # ----------------- Method to transfer contact data from Odoo to Pipedrive ---------------- #
    def transfer_contact_data(self, odoo_record, instance_id, field_model_name, dropdown_mapping_field,
                              pipedrive_model_name, field_mapper_model, type, object, logger_name, operation_type, check_hash=True):
        """
        Transfer contact data from Odoo to Pipedrive.

        This function handles the synchronization of contact data between Odoo and Pipedrive. It checks for the
        existence of a contact in Pipedrive using the contact's ID or email. If the contact exists, it updates the
        contact with the latest data from Odoo. If the contact does not exist, it creates a new contact in Pipedrive.
        The function also links the contact to an organization if applicable and logs the operations performed.

        Args:
            odoo_record (recordset or dict): The Odoo contact record to be synchronized.
            instance_id (recordset): The Pipedrive instance configuration.
            field_model_name (str): The model name for the fields mapping.
            dropdown_mapping_field (str): The dropdown mapping field name.
            pipedrive_model_name (str): The Pipedrive model name for the contact.
            field_id (str): The field ID used to fetch the contact.
            type (str): The type of contact (e.g., 'contact').
            object (str): The object type (e.g., 'person').
            logger_name (str): The name of the logger to log operations.
            check_hash (bool): Flag to check if the contact data hash has changed to avoid unnecessary updates.

        Returns:
            tuple: A tuple containing the operation performed ('update', 'no_update', 'create'), the Pipedrive record ID,
                   the Pipedrive organization ID, the partner organization ID, the contact ID, the contact email, and
                   the dynamic fields values hash.

        Raises:
            Exception: If any error occurs during the synchronization process, the error details are logged.
        """
        odoo_record_id = None
        try:
            record_data, dynamic_fields_values_hash, odoo_record_id, odoo_user_id, pipedrive_contact, api_token, headers = self.fetch_partner_pipedrive_record(
                instance_id, odoo_record, field_mapper_model, field_model_name, dropdown_mapping_field,
                pipedrive_model_name,type, object, logger_name, operation_type)
            if record_data and odoo_record and instance_id:
                sync_field = self.get_field_from_mapper('opd.contactmapper', 'odoo_id',
                                                        field_name='internal_name')
                # Ensure custom_fields exists
                if "custom_fields" not in record_data or not isinstance(record_data["custom_fields"], dict):
                    record_data["custom_fields"] = {}

                # Merge new value instead of replacing the entire dict
                record_data["custom_fields"][sync_field] = str(odoo_record_id)

                odoo_pipedrive_record_id = odoo_record.get('pipedrive_id') if isinstance(odoo_record,
                                                                                         dict) else odoo_record.pipedrive_id
                contact_email = odoo_record.get('email') if isinstance(odoo_record, dict) else odoo_record.email

                api_token = instance_id.api_token
                contact_pipedrive_id = odoo_pipedrive_record_id
                record = self.env[field_mapper_model].search([('label_name', '=', 'odoo_id')], limit=1)
                if record:
                    # Accessing the first record in the recordset
                    record_field_name = record.internal_name
                else:
                    # Handling the case where no record is found
                    record_field_name = None
                odoo_id_value = self.get_update_time_field(field_mapper_model, 'id')
                email_id_value = self.get_update_time_field(field_mapper_model, 'email')
                create_new_record = False  # Flag to indicate if a new record should be created
                if contact_pipedrive_id and contact_email:
                    filter_id = self.fetch_odoo_id(api_token, contact_pipedrive_id, odoo_id_value, type, object,
                                                   logger_name, operation_type)
                elif contact_pipedrive_id:
                    filter_id = self.fetch_odoo_id(api_token, contact_pipedrive_id, odoo_id_value, type, object,
                                                   logger_name, operation_type)
                elif contact_email:
                    filter_id = self.fetch_odoo_id(api_token, contact_email, email_id_value, type, object, logger_name, operation_type)
                    if filter_id:
                        # Fetch the record using the filter_id to check the odoo_id
                        endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?filter_id={filter_id}&api_token={api_token}'
                        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                        pipedrive_record, status_code = self.update_or_create_pipedrive_record({}, endpoint, headers,
                                                                                               logger_name, operation_type,
                                                                                               method='GET')
                        if pipedrive_record:
                            for record in pipedrive_record:
                                # existing_odoo_id = pipedrive_record[0].get(record_field_name) if isinstance(
                                #     pipedrive_record,list) else pipedrive_record.get(record_field_name)
                                existing_odoo_id = record.get(record_field_name)
                                if existing_odoo_id:
                                    description = f"The email ID {contact_email} is already associated with pipedrive contact [{record.get('name')}]. Please use a different email ID."
                                    operation = f'Record Send Odoo To Pipedrive'
                                    self.log_operation_warning(logger_name, description, operation, 'pipedrive',
                                                               pipedrive_record, operation_type, odoo_record_id)
                            return 'no_action', None, None, None, None, contact_email, None
                    else:
                        return None, None, None, None, None, None, None
                else:
                    filter_id = None
                    create_new_record = True  # Set flag to created a new record

                if filter_id:
                    endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?filter_id={filter_id}&api_token={api_token}'
                else:
                    endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}'
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
                pipedrive_record, status_code = self.update_or_create_pipedrive_record({}, endpoint, headers,
                            logger_name, operation_type,method='GET')
                pipedrive_org_id, partner_org_id = None, None

                # Accessing parent_id from odoo_record, handling both dict and object cases
                parent_id = odoo_record.get('parent_id') if isinstance(odoo_record, dict) else odoo_record.parent_id

                # Check if parent_id is a tuple and extract the ID if it is
                if isinstance(parent_id, tuple):
                    parent_id = parent_id[0]  # Extract the actual ID from the tuple
                # Check if parent_id is a recordset and extract the ID if it is
                elif hasattr(parent_id, 'id'):
                    parent_id = parent_id.id

                if parent_id:
                    parent_record = self.env['res.partner'].browse(parent_id)
                    if parent_record:
                        pipedrive_org_id = parent_record.pipedrive_id
                        partner_org_id = parent_id

                if pipedrive_record and not create_new_record:
                    pipedrive_record_id = pipedrive_record[0]['id'] if isinstance(pipedrive_record, list) else \
                        pipedrive_record['id']
                    odoo_hash = odoo_record.get('odoo_hash') if isinstance(odoo_record, dict) else odoo_record.odoo_hash
                    if not check_hash or odoo_hash != dynamic_fields_values_hash:
                        # manage user
                        pipedrive_source = pipedrive_record[0] if isinstance(pipedrive_record, list) else pipedrive_record
                        user_record = self.get_odoo_user_from_pipedrive_record(pipedrive_source)
                        if user_record and user_record.pipedrive_id:
                            pipedrive_user_id = user_record.id
                            record_data['owner_id'] = int(user_record.pipedrive_id)
                            if odoo_user_id == pipedrive_user_id:
                                record_data.pop('owner_id', None)

                        record_data['org_id'] = int(
                            pipedrive_org_id) if pipedrive_org_id else None  # Ensure organization is linked during update
                        update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_record_id}?api_token={api_token}"
                        pipedrive_record, status_code = self.update_or_create_pipedrive_record(record_data,
                                        update_endpoint, headers, logger_name, operation_type,method="PATCH")
                        self.log_operation(logger_name, status_code, odoo_record_id, record_data, 'update',
                                           'pipedrive', operation_type, parent_name=None, parent_id=None)
                        if isinstance(odoo_record, dict):
                            odoo_record = self.env['res.partner'].browse(odoo_record_id)
                            odoo_record.write(
                                {'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        else:
                            odoo_record.write(
                                {'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        odoo_record.env.cr.commit()
                        return 'update', pipedrive_record_id, pipedrive_org_id, partner_org_id, odoo_record_id, contact_email, dynamic_fields_values_hash
                    else:
                        return 'no_update', pipedrive_record_id, pipedrive_org_id, partner_org_id, odoo_record_id, contact_email, dynamic_fields_values_hash
                else:
                    if pipedrive_org_id:
                        record_data['org_id'] = int(
                            pipedrive_org_id)  # Link the organization with the contact at the time of creation
                    create_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}"
                    pipedrive_record_data, status_code = self.update_or_create_pipedrive_record(record_data,
                       create_endpoint,headers,logger_name, operation_type,method='POST')
                    if pipedrive_record_data:
                        pipedrive_record_id = pipedrive_record_data.get('id')
                        self.log_operation('contact', status_code, odoo_record_id, record_data, 'create',
                                           'pipedrive', operation_type,
                                           parent_name=None, parent_id=None)
                        if isinstance(odoo_record, dict):
                            odoo_record = self.env['res.partner'].browse(odoo_record_id)
                            odoo_record.write(
                                {'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        else:
                            odoo_record.write(
                                {'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        odoo_record.env.cr.commit()
                        return 'create', pipedrive_record_id, pipedrive_org_id, partner_org_id, odoo_record_id, contact_email, dynamic_fields_values_hash
                    return None, None, None, None, None, None, None
            else:
                return None, None, None, None, None, None, None

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while contact create/update in pipedrive.'
            self.exception_log_error(error_details, 'contact', description, 'pipedrive', operation_type, odoo_record_id, error_type)
            return None, None, None, None, None, None, None

    # --------------------------- Proces Activity Based On Check-box Ticked ---------------------- #
    def should_process_partner_activity(self, instance_id, odoo_activity_type, is_contact=True):
        """
    Check if the specific contact-related or company-related activity type checkbox is checked.

    Args:
        instance_id: The Pipedrive instance ID.
        odoo_activity_type (int): The ID of the specific activity type to check:
                                  1 for Email, 2 for Call, 3 for Meeting, 4 for To-Do.
        is_contact (bool): Flag to indicate whether to check contact-related checkboxes.
                           If False, company-related checkboxes will be checked.

    Returns:
        bool: True if the relevant checkbox for the activity type is checked, False otherwise.
    """
        if is_contact:
            if odoo_activity_type == 1:
                return instance_id.is_contact_emails
            elif odoo_activity_type == 2:
                return instance_id.is_contact_calls
            elif odoo_activity_type == 3:
                return instance_id.is_contact_meetings
            elif odoo_activity_type == 4:
                return instance_id.is_contact_tasks
        else:
            if odoo_activity_type == 1:
                return instance_id.is_company_emails
            elif odoo_activity_type == 2:
                return instance_id.is_company_calls
            elif odoo_activity_type == 3:
                return instance_id.is_company_meetings
            elif odoo_activity_type == 4:
                return instance_id.is_company_tasks
        return False

    # --------------------------- Proces Activity Based On Check-box Ticked ---------------------- #

    def should_process_crm_activity(self, instance_id, crm_type, activity_type_id):
        """
        Check if any of the contact-related or company-related checkboxes are checked.

        Args:
            instance_id: The Pipedrive instance ID.
            crm_type (str): The type of CRM activity, e.g., 'lead' or 'deal'.
            activity_type_id (int): The ID of the specific activity to check:
                                1 for Email, 2 for Call, 3 for Meeting, 4 for To-Do.

        Returns:
            bool: True if any relevant checkbox is checked, False otherwise.
        """
        if crm_type == 'lead':
            if activity_type_id == 1:
                return instance_id.is_lead_emails
            elif activity_type_id == 2:
                return instance_id.is_lead_calls
            elif activity_type_id == 3:
                return instance_id.is_lead_meetings
            elif activity_type_id == 4:
                return instance_id.is_lead_tasks
        elif crm_type == 'opportunity':
            if activity_type_id == 1:
                return instance_id.is_deal_emails
            elif activity_type_id == 2:
                return instance_id.is_deal_calls
            elif activity_type_id == 3:
                return instance_id.is_deal_meetings
            elif activity_type_id == 4:
                return instance_id.is_deal_tasks
        return False

    # -------------------------------- Handle Activities and Notes For Odoo Company and Contact -------------------- #
    def handle_activities_and_notes(self, instance_id, odoo_record, operation_type, is_contact=True, is_activity=True):
        """
           Handles the synchronization of activities and notes between Odoo and Pipedrive.

           Args:
               instance_id (object): The Pipedrive instance configuration record.
               is_note_name (bool): Indicates if the note name should be used.
               odoo_record (object): The Odoo record for which activities and notes are processed.
               pipedrive_record_id (int): The corresponding Pipedrive record ID.
               is_contact (bool, optional): Flag to indicate if the record is a contact. Defaults to True.

           """
        odoo_record_id = self.get_record_id(odoo_record)
        odoo_activities = self.env['mail.activity'].search(
            [('res_id', '=', odoo_record_id), ('res_model', '=', 'res.partner'), ('active', '=', True)])
        odoo_notes = self.env['mail.message'].search(
            [('res_id', '=', odoo_record_id), ('model', '=', 'res.partner'), ('message_type', '=', 'comment')])
        api_token = instance_id.api_token

        if is_contact:
            last_sync_date = instance_id.odoo_contact_last_sync_date
        else:
            last_sync_date = instance_id.odoo_company_last_sync_date
        # Process activities
        if odoo_activities:
            for odoo_activity in odoo_activities:
                activity_update_time = odoo_activity.get('write_date') if isinstance(odoo_activity,
                                                                                     dict) else odoo_activity.write_date
                # activity_update_time = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S')
                if activity_update_time > last_sync_date or not is_activity:
                    activity_type = odoo_activity.get('activity_type_id') if isinstance(odoo_activity,
                                                                                        dict) else odoo_activity.activity_type_id
                    activity_type_id = activity_type.get('id') if isinstance(activity_type, dict) else activity_type.id
                    if self.should_process_partner_activity(instance_id, activity_type_id, is_contact):
                        self.env['mail.activity'].create_or_update_pipedrive_activity(api_token, odoo_activity, operation_type)

        # Process notes if is_notes is checked
        is_checked = instance_id.is_contact_notes if is_contact else instance_id.is_company_notes
        if is_checked:
            if odoo_notes:
                for odoo_note in odoo_notes:
                    note_update_time = odoo_note.get('write_date') if isinstance(odoo_note,
                                                                                 dict) else odoo_note.write_date
                    if note_update_time > last_sync_date or not is_activity:
                        self.env['mail.activity'].create_or_update_pipedrive_notes(api_token, odoo_note, operation_type)
            else:
                _logger.info('No notes found for Odoo record with ID %s.', odoo_record_id)

    # ------------------------- Send Contact Related Data From Odoo To Pipedrive --------------------- #
    def handle_contact_related_data(self, instance_id, contact_id, partner_org_id, pipedrive_record_id, operation_type):
        """
           Handles the synchronization of related data for contacts between Odoo and Pipedrive.

           Args:
               instance_id (object): The Pipedrive instance configuration record.
               contact_id (int): The contact ID in Odoo.
               partner_org_id (int): The organization ID related to the contact.
               pipedrive_record_id (int): The corresponding Pipedrive record ID.
        """
        api_token = instance_id.api_token
        if instance_id.odoo_contact_related_companies and partner_org_id and pipedrive_record_id:
            self.odoo_contact_related_companies(instance_id, partner_org_id, pipedrive_record_id, api_token,
              'res.partner','organizations', 'pipedriveinstance.companies.lines',
              'odoo_company_dropdown_mapping', operation_type)

        if instance_id.odoo_contact_related_leads and pipedrive_record_id:
            self.env['crm.lead'].odoo_contact_related_crm_data(instance_id, contact_id, pipedrive_record_id, api_token,
            'crm.lead', 'leads', 'pipedriveinstance.leads.lines',
            'odoo_lead_dropdown_mapping', 'lead', 'lead', operation_type)

        if instance_id.odoo_contact_related_deals and pipedrive_record_id:
            self.env['crm.lead'].odoo_contact_related_crm_data(instance_id, contact_id, pipedrive_record_id, api_token,
            'crm.lead', 'deals', 'pipedriveinstance.deals.lines',
            'odoo_deal_dropdown_mapping', 'opportunity', 'deal', operation_type)

    # ----------------------- Send Company Related Data From Odoo To Pipedrive ----------------- #
    def handle_company_related_data(self, instance_id, odoo_id, pipedrive_record_id, api_token, operation_type):
        """
            Handles the synchronization of company-related data between Odoo and Pipedrive.

            This function checks for related contacts, leads, and deals for a given instance and performs
            the necessary data synchronization between Odoo and Pipedrive.

            Parameters:
                instance_id (object): The instance containing the configuration and data.
                odoo_id (int): The Odoo record ID.
                pipedrive_record_id (int): The Pipedrive record ID.
                api_token (str): The API token for authenticating with Pipedrive.
                logger_name (str): The name of the logger to use for logging operations.

            Returns:
                None
            """
        if instance_id.odoo_company_related_contacts and odoo_id:
            self.odoo_company_related_contacts(instance_id, odoo_id, api_token, 'res.partner',
                                               'persons', 'pipedriveinstance.contacts.lines',
                                               'odoo_contacts_dropdown_mapping', operation_type)
        if instance_id.odoo_company_related_leads and pipedrive_record_id:
            self.env['crm.lead'].odoo_company_related_crm_data(instance_id, odoo_id, pipedrive_record_id, api_token,
                                                               'crm.lead', 'lead', 'leads',
                                                               'pipedriveinstance.leads.lines',
                                                               'odoo_lead_dropdown_mapping', 'lead', operation_type)
        if instance_id.odoo_company_related_deals and pipedrive_record_id:
            self.env['crm.lead'].odoo_company_related_crm_data(instance_id, odoo_id, pipedrive_record_id, api_token,
                                                               'crm.lead', 'opportunity', 'deals',
                                                               'pipedriveinstance.deals.lines',
                                                               'odoo_deal_dropdown_mapping', 'deal', operation_type)

    # ------------------------ Pipedrive version2 company payload -------------------------- #

    def build_pipedrive_v2_payload(self, record_data, logger_name):
        """
        Convert v1-style flat mapped record_data → proper v2 Pipedrive payload.
        record_data stays unchanged in hash logic.
        """
        payload = {}
        address = {}

        # Temporary storage for concatenation
        address_value = record_data.get("address")
        country = record_data.get("address_country")
        state = record_data.get("address_admin_area_level_1")
        city = record_data.get("address_locality")
        postal = record_data.get("address_postal_code")

        for key, value in record_data.items():

            if key == 'address':
                address['value'] = value
            elif key == 'address_country':
                address['address_country'] = value
            elif key == 'address_admin_area_level_1':
                address['address_admin_area_level_1'] = value
            elif key == 'address_locality':
                address['address_locality'] = value
            elif key == 'address_postal_code':
                address['address_postal_code'] = value

            # ------------------ NORMAL FIELDS ------------------
            else:
                payload[key] = value


        # Attach address only if exists
        if logger_name == "company" and address:

            # Build a clean formatted value
            parts = [address_value, city, state, country, postal]
            formatted = ", ".join([p for p in parts if p])  # skip None/empty

            address['value'] = formatted

            # Attach only if at least something exists
            if address:
                payload['address'] = address

        return payload

    # ------------------------ Pipedrive version2 contact payload -------------------------- #
    def build_pipedrive_v2_contact_payload(self, record_data):
        """
        Convert v1-style flat mapped record_data → Pipedrive v2 Contact payload.
        record_data stays unchanged for hash calculation.
        """

        payload = {}
        # -------------------------
        # 1. CONTACT STRUCTURE
        # -------------------------
        phones_list = []
        emails_list = []

        # -------------------------
        # 2. Extract Fields
        # -------------------------
        for key, value in record_data.items():

            # ----- PHONE HANDLING -----
            if key == "phone":
                if value:
                    phones_list.append({
                        "label": "work",
                        "value": value,
                        "primary": True
                    })
                continue

            # ----- EMAIL HANDLING -----
            if key == "email":
                if value:
                    emails_list.append({
                        "label": "work",
                        "value": value,
                        "primary": True
                    })
                continue

            # ----- NORMAL FIELDS -----
            payload[key] = value

        # -------------------------
        # 3. Attach Phones/Emails (If exists)
        # -------------------------
        if phones_list:
            payload["phones"] = phones_list

        if emails_list:
            payload["emails"] = emails_list

        return payload

    # ---------------------- Send Company And Company Related Data From Odoo To Pipedrive -------------------- #
    def handle_company_record(self, instance_id, odoo_record, field_model_name, pipedrive_model_name,
                              field_mapper_model, dropdown_mapping_field,
                              model_name, type, object, logger_name, operation_type, check_hash=True):
        """
            Handles the creation or updating of a company record between Odoo and Pipedrive.

            This function checks if a Pipedrive record exists for a given Odoo record. If it exists and the
            data has changed, it updates the Pipedrive record. If it does not exist, it creates a new record
            in Pipedrive. It also handles related activities and notes synchronization.

            Parameters:
                instance_id (object): The instance containing the configuration and data.
                odoo_record (object): The Odoo record to be synchronized.
                record (list): The existing record data from Pipedrive, if any.
                is_notes_name (str): The name indicating whether to handle notes.
                pipedrive_model_name (str): The model name in Pipedrive.
                record_data (dict): The data to be sent to Pipedrive.
                dynamic_fields_values_hash (str): The hash value of the dynamic fields to check for changes.
                model_name (str): The name of the Odoo model.
                headers (dict): The headers for the API request.
                api_token (str): The API token for authenticating with Pipedrive.
                logger_name (str): The name of the logger to use for logging operations.
                check_hash(Bool): Check Odoo Hash based on Check hash True or False
            Returns:
                str: 'update' if the record was updated, 'create' if a new record was created, 'no_update' if no changes were made,
                     None if an error occurred.
        """
        odoo_record_id = None
        try:
            record_data, dynamic_fields_values_hash, odoo_record_id, odoo_user_id, record, api_token, headers = self.fetch_partner_pipedrive_record(
                instance_id, odoo_record, field_mapper_model, field_model_name, dropdown_mapping_field,
                pipedrive_model_name, type, object, logger_name, operation_type)
            if record_data and odoo_record and instance_id:
                sync_field = self.get_field_from_mapper('opd.companymapper', 'odoo_id',
                                                        field_name='internal_name')
                # Ensure custom_fields exists
                if "custom_fields" not in record_data or not isinstance(record_data["custom_fields"], dict):
                    record_data["custom_fields"] = {}

                # Merge new value instead of replacing the entire dict
                record_data["custom_fields"][sync_field] = str(odoo_record_id)
                if isinstance(odoo_record, dict):
                    record_hash = odoo_record.get('odoo_hash')
                else:
                    record_hash = odoo_record.odoo_hash

                if record:
                    pipedrive_record_id = record[0].get('id') if isinstance(record, list) else record.get('id')
                    if not check_hash or record_hash != dynamic_fields_values_hash:
                        # manage user
                        pipedrive_source = record[0] if isinstance(record, list) else record
                        user_record = self.get_odoo_user_from_pipedrive_record(pipedrive_source)
                        if user_record and user_record.pipedrive_id:
                            pipedrive_user_id = user_record.id
                            record_data['owner_id'] = int(user_record.pipedrive_id)
                            if odoo_user_id == pipedrive_user_id:
                                record_data.pop('owner_id', None)
                        partner = self.env[model_name].browse(odoo_record_id)
                        partner.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        partner.env.cr.commit()
                        update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_record_id}?api_token={api_token}"
                        response = requests.request("PATCH", update_endpoint, headers=headers,
                                                    data=json.dumps(record_data))
                        if response.status_code != 200:
                            # Log the error with HTTP status code
                            description = f'Error occurred while send record to pipedrive'
                            self.http_log_error(f"No record found: {response.text}", logger_name, description,
                                                record_data, response.text, 'pipedrive', operation_type, odoo_record_id, f"HTTP {response.status_code}")
                            return None
                        else:
                            self.log_operation(logger_name, response.status_code, odoo_record_id, record_data,
                                               'update', 'pipedrive', operation_type,
                                               parent_name=None, parent_id=None)
                            self.handle_company_related_data(instance_id, odoo_record_id, pipedrive_record_id,
                                                             api_token, operation_type)
                            if not check_hash:
                                self.handle_activities_and_notes(instance_id, odoo_record, operation_type,
                                                                 is_contact=False, is_activity=False)
                            else:
                                self.handle_activities_and_notes(instance_id, odoo_record, operation_type,
                                                                 is_contact=False, is_activity=True)

                            return 'update'
                    else:
                        return 'no_update'
                else:
                    create_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}"
                    create_payload = json.dumps(record_data)
                    response = self.fetch_data(create_endpoint, headers, create_payload, method="POST")
                    if response.status_code in [200, 201]:
                        response_json = response.json()
                        new_record = response_json.get('data', [])
                        pipedrive_record_id = new_record.get('id')
                        self.log_operation(logger_name, response.status_code, odoo_record_id, create_payload,
                                           'create',
                                           'pipedrive', operation_type,
                                           parent_name=None, parent_id=None)
                        odoo_record_id = self.get_record_id(odoo_record)
                        partner = self.env[model_name].browse(odoo_record_id)
                        partner.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                        partner.env.cr.commit()
                        self.handle_company_related_data(instance_id, odoo_record_id, pipedrive_record_id, api_token, operation_type)
                        if not check_hash:
                            self.handle_activities_and_notes(instance_id, odoo_record, operation_type,
                                                             is_contact=False, is_activity=False)
                        else:
                            self.handle_activities_and_notes(instance_id, odoo_record, operation_type,
                                                             is_contact=False, is_activity=True)
                        return 'create'
                    else:
                        # Log the error with HTTP status code
                        description = f'Error occured while create/update {logger_name}'
                        self.http_log_error(f"No record found: {response.text}", logger_name, description,
                                            record_data, response.text, 'pipedrive', operation_type, odoo_record_id, f"HTTP {response.status_code}")
                        return None
            else:
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, odoo_record_id, error_type)
            return None

    # ---------------------- Validate pagination parameters --------------------- #
    @api.model
    def initialize_pagination(self, instance_id, logger_name, model_name, operation_type):
        """
        Initialize and validate pagination parameters.

        Args:
            instance_id: The Pipedrive instance ID.

        Returns:
            A tuple containing the limit and offset for pagination.

        Raises:
            UserError: If the pagination size is less than or equal to zero.
        """
        pagination_size = instance_id.pagination_size

        if pagination_size <= 0:
            description = _('Pagination size should be greater than zero.')
            operation = _('%s send pipedrive to odoo') % logger_name
            self.log_operation_warning(logger_name, description, operation, model_name, '', operation_type, '')
            return 0, 0
        limit = pagination_size
        offset = 0

        return limit, offset

    # ------------------------------ Get Odoo Record ID ---------------------------- #
    @api.model
    def get_record_id(self, odoo_record):
        if isinstance(odoo_record, dict):
            return odoo_record.get('id')
        else:
            return odoo_record.id

    # ----------------------- Fetch Particular Fields From Odoo Record ------------------ #
    def fetch_odoo_records(self, field_model_name, instance_id, model_name, additional_fields, record_last_id, logger_name, operation_type,
                           is_company=None,
                           crm_type=None,
                           last_sync_date=None, offset=0, limit=0):
        """
            Fetch records from the specified model with the defined fields and filters.

            field_model_name: Name of the model to fetch field mappings from
            model_name: Name of the model to fetch records from
            additional_fields: List of additional fields to fetch
            is_company: Company filter value (optional)
            crm_type: CRM type filter value (optional)
            last_sync_date: Date filter for write_date (optional)
            offset: Offset for pagination (optional)
            limit: Limit for pagination (optional)
            return: List of fetched records

        """

        # Step 1: Fetch field mappings from the specified model
        field_mappings = self.get_fields_lines_data(field_model_name, instance_id)
        if not field_mappings:
            description = f"Field Mapping is required for {logger_name.capitalize()}"
            operation = f'{logger_name.capitalize()} Record Sync Pipedrive To Odoo'
            self.log_operation_warning(logger_name, description, operation, 'pipedrive', '',
                                       operation_type, '')
            return None
        # Step 2: Build a list of fields to fetch from the specified model based on the mapping
        fields_to_fetch = []
        for mapping in field_mappings:
            odoo_field = mapping.odoo_fields_record.label_name
            fields_to_fetch.append(odoo_field)

        # Add additional fields to fetch
        fields_to_fetch.extend(additional_fields)

        # Step 3: Build domain for search_read
        domain = [
            ('write_date', '>', last_sync_date),
            ('sync_to_pipedrive', '=', 'yes'),
            ('id', '>', record_last_id),
            ('active', '=', True)
        ]
        if is_company is not None:
            domain.append(('is_company', '=', is_company))
        if crm_type is not None:
            domain.append(('type', '=', crm_type))

        # Step 4: Fetch records from the specified model with the defined fields and filters
        odoo_records = self.env[model_name].search_read(
            domain,fields=fields_to_fetch,offset=offset,limit=limit,order='id ASC')

        return odoo_records

    # --------------------- Fetch Particular Odoo Record Fields For Related Module --------------- #
    def fetch_related_odoo_records(self, field_model_name, model_name, additional_fields, domain
                                   , offset=None, limit=None):
        """
            Fetch records from the specified model with the defined fields and filters.

            field_model_name: Name of the model to fetch field mappings from
            model_name: Name of the model to fetch records from
            additional_fields: List of additional fields to fetch
            is_company: Company filter value (optional)
            crm_type: CRM type filter value (optional)
            last_sync_date: Date filter for write_date (optional)
            offset: Offset for pagination (optional)
            limit: Limit for pagination (optional)
            return: List of fetched records

        """

        instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
        # Step 1: Fetch field mappings from the specified model
        field_mappings = self.get_fields_lines_data(field_model_name, instance_id)

        # Step 2: Build a list of fields to fetch from the specified model based on the mapping
        fields_to_fetch = []
        for mapping in field_mappings:
            odoo_field = mapping.odoo_fields_record.label_name
            fields_to_fetch.append(odoo_field)

        # Add additional fields to fetch
        fields_to_fetch.extend(additional_fields)

        # Step 4: Fetch records from the specified model with the defined fields and filters
        odoo_records = self.env[model_name].search_read(
            domain,fields=fields_to_fetch,offset=offset,limit=limit,order='id ASC')

        return odoo_records

    # ------------------------------ Data Transfer From Odoo To Pipedrive -----------------------------#

    def fetch_all_odoo_partner_data(self, instance_id, model_name, last_sync_date_field, pipedrive_model_name,
        field_model_name,field_mapper_model, type, object, dropdown_mapping_field, is_company, logger_name, operation_type):
        """
            Transfer data from Odoo to Pipedrive for all companies.

            Args:
                instance_id: The Pipedrive instance ID.
                model_name: The name of the Odoo model containing company data.
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

            last_sync_date, current_utc_time = self.last_sync_date_common(last_sync_date_field)

            limit, offset = self.initialize_pagination(instance_id, logger_name, 'pipedrive', operation_type)
            if limit == 0:
                return
            if is_company:
                record_last_id = instance_id.odoo_company_last_id
            else:
                record_last_id = instance_id.odoo_contact_last_id

            while True:

                if is_company:
                    additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'is_company', 'write_date',
                                         'sync_to_pipedrive']
                else:
                    additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'is_company', 'write_date',
                                         'parent_id', 'sync_to_pipedrive']

                partner_records = self.fetch_odoo_records(field_model_name, instance_id, model_name,
                                                          additional_fields, record_last_id, logger_name, operation_type,
                                                          is_company=is_company, crm_type=None,
                                                          last_sync_date=last_sync_date, offset=0, limit=limit)

                if not partner_records:
                    break

                for partner_record in partner_records:
                    if model_name == 'res.partner':
                        if is_company:
                            self.handle_company_record(instance_id, partner_record, field_model_name,
                                                       pipedrive_model_name, field_mapper_model,
                                                       dropdown_mapping_field,model_name, type, object, logger_name,
                                                       operation_type,check_hash=True)
                        else:
                            status, pipedrive_record_id, pipedrive_org_id, partner_org_id, contact_id, contact_email, dynamic_fields_values_hash = self.transfer_contact_data(
                                partner_record, instance_id, field_model_name, dropdown_mapping_field,
                                pipedrive_model_name, field_mapper_model, type, object, logger_name, operation_type,
                                check_hash=True)

                            if status == 'create' or status == 'update':
                                self.handle_contact_related_data(instance_id, contact_id, partner_org_id,
                                                                 pipedrive_record_id, operation_type)
                                self.handle_activities_and_notes(instance_id, partner_record, operation_type,
                                                                 is_contact=True, is_activity=True)

                record_last_id = partner_records[-1].get('id') if isinstance(partner_records[-1],
                                                                             dict) else partner_records[-1].id
                if is_company:
                    instance_id.write({'odoo_company_last_id': record_last_id})
                else:
                    instance_id.write({'odoo_contact_last_id': record_last_id})
                instance_id.env.cr.commit()

                if len(partner_records) < limit:
                    break

            # Update last sync date regardless of condition
            if is_company:
                instance_id.write(
                    {'odoo_company_last_sync_date': current_utc_time})
                instance_id.write({'odoo_company_last_id': 0})
            else:
                instance_id.write(
                    {'odoo_contact_last_sync_date': current_utc_time})
                instance_id.write({'odoo_contact_last_id': 0})

            self.env['opd.mapper.mixin'].scheduler_run_successfully_log(logger_name, operation_type,
                                                                        'pipedrive')

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while {logger_name} create/update in pipedrive.'
            self.exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, '', error_type)

    # get odoo product cost value
    def get_odoo_product_cost(self, record):
        """
        Safely extract product cost (standard_price) from either:
        - product.product record
        - product.template record
        - dict-based record
        - fallback default 0

        Returns:
            float: standard_price value
        """
        try:
            # If record is ORM model (product.product or product.template)
            if hasattr(record, "standard_price"):
                return float(record.standard_price or 0)

            # If record is a dict
            if isinstance(record, dict):
                return float(record.get("standard_price", 0))

        except Exception:
            pass  # fallback

        return 0.0

    # ---------------------------------------------------------
    #  Convert Odoo tag_ids → Pipedrive label_ids list
    # ---------------------------------------------------------
    def map_lead_tags_from_odoo(self, tag_records, instance_id):
        """
        Convert Odoo crm.tag → Pipedrive label_ids.
        Works for: recordset, single id, list of ids.
        """
        # ----------------------------------------------------------
        # Normalize tag_records → always a recordset
        # ----------------------------------------------------------
        if not tag_records:
            return []

        Tag = self.env['crm.tag']

        # Case 1: tag_records is a recordset → OK
        if isinstance(tag_records, models.Model):
            tags = tag_records

        # Case 2: tag_records is a list/tuple of IDs
        elif isinstance(tag_records, (list, tuple)):
            tags = Tag.browse(tag_records)

        # Case 3: tag_records is a single integer ID
        elif isinstance(tag_records, int):
            tags = Tag.browse([tag_records])

        else:
            # Unknown type
            return []

        # ----------------------------------------------------------
        # Do the sync
        # ----------------------------------------------------------
        api_token = instance_id.api_token
        url = f"{self.__API_BASE_URL}leadLabels?api_token={api_token}"
        headers = {'Content-Type': 'application/json'}

        label_ids = []

        for tag in tags:

            # Already synced
            if tag.pipedrive_id:
                label_ids.append(str(tag.pipedrive_id))
                continue

            # Create tag in Pipedrive
            payload = {
                "name": tag.name,
                "color": "gray",
            }

            response = requests.post(url, json=payload, headers=headers)

            if response.status_code in (200, 201):
                data = response.json().get("data")
                if data:
                    pd_id = data.get("id")

                    # store new pipedrive id
                    tag.write({"pipedrive_id": pd_id})
                    label_ids.append(str(pd_id))

            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = "Lead tag sync Odoo → Pipedrive failed"
                self.http_log_error(
                    error_details, "lead", description,
                    payload, response.text,
                    "pipedrive", "manually",
                    tag.id, f"HTTP {response.status_code}"
                )

        return label_ids

    # ----------------------------- Odoo To Pipedrive Field Mapping Function --------------------------- #
    def odoo_to_pipedrive_map_fields(self, record, instance_id, field_model_name, dropdown_mapping_field, record_id, logger_name, operation_type):
        """
        Map Pipedrive fields to Odoo fields using the provided mappings.

        Args: 'pipedriveinstance.companies.lines'
            record (dict): A dictionary containing Pipedrive record data.
            instance_id (str): The Pipedrive instance ID.
            field_model_name (str): The name of the model containing field mappings between Pipedrive and Odoo.
            dropdown_mapping_field (str): The name of the field in `instance_id` containing dropdown mapping information.
        Returns:
            dict: A dictionary containing mapped data for Odoo fields.
        """
        field_mapping = {}
        operation_status = None
        mapping = {}

        dropdown_field = getattr(instance_id, dropdown_mapping_field, None)
        if dropdown_field:
            mapping = json.loads(dropdown_field)

        fields_lines_data = self.get_fields_lines_data(field_model_name, instance_id)

        for data in fields_lines_data:
            odoo_field_data = data['odoo_fields_record']
            pipedrive_field_data = data['pipedrive_fields_record']
            internal_name = pipedrive_field_data.internal_name
            label_name = odoo_field_data.label_name
            field_mapping[label_name] = internal_name
        record_data = {}
        temp_data = {}

        if not field_mapping:
            description = f"Field Mapping is required for {logger_name.capitalize()}"
            operation = f'{logger_name.capitalize()} Record Sync Odoo To Pipedrive'
            self.log_operation_warning(logger_name, description, operation, 'pipedrive', record, operation_type, record_id)
            return record_data, '', operation_status

        # Process the record, whether it's a list of records or a single record
        records = record if isinstance(record, list) else [record]

        for record in records:
            for label_name, internal_name in field_mapping.items():
                record_field_data = record.get(label_name) if isinstance(record, dict) else getattr(record, label_name,
                                                                                                    False)
                if record_field_data:
                    if isinstance(record_field_data, tuple):  # Handle tuple fields
                        record_field_data = record_field_data[0]

                    # Extract the ID from record_field_data if it is a recordset
                    if hasattr(record_field_data, 'id'):
                        record_field_data = record_field_data.id
                    else:
                        record_field_data = record_field_data
                    if label_name == 'state_id':
                        state_id = record_field_data
                        state = self.env['res.country.state'].search([('id', '=', state_id)],
                                                                     limit=1)
                        state_name = state.name
                        if state:
                            record_data[internal_name] = state_name
                            temp_data[internal_name] = state_id
                    elif label_name == 'country_id':
                        country_id = record_field_data
                        country = self.env['res.country'].search([('id', '=', country_id)],
                                                                 limit=1)
                        con_name = country.name
                        if country:
                            record_data[internal_name] = con_name
                            temp_data[internal_name] = country_id
                    elif label_name == 'id':
                        record_data[internal_name] = str(record_field_data)
                        # Extract description from Odoo note
                    elif label_name == 'probability':
                        temp_data["probability"] = int(round(float(record_field_data)))
                        record_data["probability"] = int(round(float(record_field_data)))
                    elif label_name == 'description':
                            record_data[internal_name] = re.sub(r'<[^>]+>', '', record_field_data)
                            temp_data[internal_name] = re.sub(r'<[^>]+>', '', record_field_data)
                    elif internal_name == 'price':
                        if "prices" not in record_data:
                            record_data["prices"] = []
                        cost_value = self.get_odoo_product_cost(record)
                        record_data["prices"].append({
                            "price": float(record_field_data),
                            "currency": "USD",  # Default to USD if no currency is provided
                            "cost": cost_value,
                        })
                    elif label_name == 'stage_id':
                        if isinstance(record_field_data, tuple):
                            stage_id = str(record_field_data[0])  # Extract the ID from the tuple
                            stage_name = record_field_data[1]  # Extract the name from the tuple
                        elif isinstance(record_field_data, int):
                            stage_id = str(record_field_data)
                            stage_name = mapping[label_name].get(stage_id,
                                                                 None)  # Assuming you have a mapping to get the name
                        else:
                            stage_id = str(record_field_data)
                            stage_name = record_field_data
                        if stage_name in ['won', 'lost']:
                            record_data['status'] = mapping[label_name].get(stage_id)
                            temp_data[internal_name] = stage_id
                        else:
                            organization_value = str(record_field_data)
                            odoo_value = mapping[label_name].get(organization_value)
                            if odoo_value:
                                record_data['status'] = 'open'
                                temp_data[internal_name] = organization_value
                                record_data[internal_name] = odoo_value
                            else:
                                description = (f'Please review and correct the dropdown configuration '
                                               f'{internal_name} mapping as the selected {logger_name} does not '
                                               f'match the configured options. Once corrected the {logger_name} '
                                               f'{internal_name}, and please try again. {logger_name} ID: {record_id}')
                                operation = f'{logger_name} send odoo to pipedrive'
                                self.log_operation_warning(logger_name, description, operation, 'pipedrive', record, operation_type, record_id)
                                operation_status = 'skip'
                                continue
                    elif label_name in mapping:
                        organization_value = str(record_field_data)
                        odoo_value = mapping[label_name].get(organization_value)
                        if odoo_value:
                            if label_name == 'sync_to_pipedrive' and logger_name != 'lead':
                                record_data['custom_fields'] = {internal_name: int(odoo_value)}
                            else:
                                record_data[internal_name] = odoo_value
                            temp_data[internal_name] = organization_value
                        else:
                            description = (f'Please review and correct the dropdown configuration '
                                           f'{internal_name} mapping as the selected {logger_name} does not '
                                           f'match the configured options. Once corrected the {logger_name} '
                                           f'{internal_name}, and please try again. {logger_name} ID: {record_id}')
                            operation = f'{logger_name} send odoo to pipedrive'
                            self.log_operation_warning(logger_name, description, operation, 'pipedrive', record, operation_type, record_id)
                            operation_status = 'skip'
                            continue
                    else:
                        record_data[internal_name] = record_field_data
                        temp_data[internal_name] = record_field_data
                else:
                    record_data[internal_name] = None
                    temp_data[internal_name] = None
                    if internal_name == 'price':
                        if "prices" not in record_data:
                            record_data["prices"] = []
                        cost_value = self.get_odoo_product_cost(record)
                        record_data["prices"].append({
                            "price": float(record_field_data),
                            "currency": "USD",  # Default to USD if no currency is provided
                            "cost": cost_value,
                        })
                    if internal_name in ['code', 'description']:
                        record_data[internal_name] = ''
                        temp_data[internal_name] = None
                    if internal_name == 'probability':
                        record_data['probability'] = 0
                        temp_data[internal_name] = 0
                    if internal_name == 'address_admin_area_level_1':
                        record_data['address_admin_area_level_1'] = ''
                    if internal_name == 'address_country':
                        record_data['address_country'] = ''
                    if internal_name == 'address_postal_code':
                        record_data['address_postal_code'] = ''
                    if internal_name == 'address_locality':
                        record_data['address_locality'] = ''
                    if internal_name == 'stage_id':
                        description = (f'Please review and correct the dropdown configuration '
                                       f'{internal_name} mapping as the selected {logger_name} does not '
                                       f'match the configured options. Once corrected the {logger_name} '
                                       f'{internal_name}, and please try again. {logger_name} ID: {record_id}')
                        operation = f'{logger_name} send odoo to pipedrive'
                        self.log_operation_warning(logger_name, description, operation, 'pipedrive', record, operation_type, record_id)
                        operation_status = 'skip'
                        continue

                if internal_name == 'expected_close_date' and temp_data['expected_close_date']:
                    temp_data['expected_close_date'] = temp_data['expected_close_date'].strftime('%Y-%m-%d')

                # ----------------------------------------------------------
                #  SPECIAL HANDLING FOR LEAD tag_ids → Pipedrive label_ids
                # ----------------------------------------------------------
                if logger_name == 'lead':
                    tags = record['tag_ids'] if isinstance(record, dict) else record.tag_ids
                    label_ids = self.map_lead_tags_from_odoo(tags, instance_id)

                    if label_ids:
                        record_data['label_ids'] = label_ids

        # Mapped Data Generation
        mapped_data = self.prepare_mapped_data_pipedrive_and_odoo(temp_data, mapping)
        # Fields to exclude
        exclude_fields = ['price', 'cost', 'tag_ids']
        # Filter out the fields to exclude
        filtered_mapped_data = {k: v for k, v in mapped_data.items() if k not in exclude_fields}
        # Calculating Hash
        dynamic_fields_values_hash = self.calculate_hash(filtered_mapped_data)

        return record_data, dynamic_fields_values_hash, operation_status

    # ------------------------------- Fetch Partner Pipedrive Record -------------------------------------- #
    def fetch_partner_pipedrive_record(self, instance_id, odoo_record, field_mapper_model, field_model_name,
        dropdown_mapping_field,pipedrive_model_name, type, object, logger_name, operation_type):
        """
        Fetch Pipedrive record corresponding to an Odoo record.

        Args:
            instance_id: The Pipedrive instance ID.
            odoo_record: The Odoo record to be synchronized.
            field_mapper_model: The name of the model containing field mappings between Pipedrive and Odoo.
            dropdown_mapping_field: The name of the field in `instance_id` containing dropdown mapping information.
            pipedrive_model_name: The name of the Pipedrive model.
            type: The type of the field.
            object: The object type.
            logger_name: The name of the logger to use for logging operations.

        Returns:
            tuple: (record_data, dynamic_fields_values_hash, odoo_record_id, record, api_token)
        """
        odoo_record_id = odoo_record.get('id') if isinstance(odoo_record, dict) else odoo_record.id
        odoo_pipedrive_record_id = odoo_record.get('pipedrive_id') if isinstance(odoo_record, dict) else odoo_record.pipedrive_id
        record_data, dynamic_fields_values_hash, operation_status = self.odoo_to_pipedrive_map_fields(odoo_record, instance_id,
          field_model_name,dropdown_mapping_field,odoo_record_id, logger_name, operation_type)
        if operation_status == 'skip':
            return None, None, None, None, None, None, None
        if logger_name == 'company':
            record_data = self.build_pipedrive_v2_payload(record_data, logger_name)
        else:
            record_data = self.build_pipedrive_v2_contact_payload(record_data)

        api_token = instance_id.api_token if 'api_token' in instance_id else None
        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
        if record_data:
            # Set owner_id at Pipedrive side
            odoo_user_id = self.env['res.users'].set_record_data(odoo_record, 'user_id', 'owner_id', record_data)
            if odoo_pipedrive_record_id:
                endpoint = f'{instance_id.api_base_url}/{pipedrive_model_name}/{odoo_pipedrive_record_id}?api_token={api_token}'

                # Make a GET request to the API endpoint
                response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, {}, method="GET")
                if response and response.status_code != 200:
                    # Log the error with HTTP status code
                    description = f'Error occurred while filtering records'
                    self.http_log_error(f"No record found: {response.text}", logger_name, description,
                                        {}, response.text, 'pipedrive', operation_type, odoo_record_id, f"HTTP {response.status_code}")
                    return None, None, None, None, None, None, None

                response_json = response.json()
                record = response_json.get('data', [])

                return record_data, dynamic_fields_values_hash, odoo_record_id, odoo_user_id, record, api_token, headers
            else:
                return record_data, dynamic_fields_values_hash, odoo_record_id, odoo_user_id, {}, api_token, headers


        else:
            return None, None, None, None, None, None, None

    # ------------------- Fetch Filter ID For Related Odoo ID ------------- #
    def fetch_odoo_id(self, api_token, odoo_id, field_id, type, object, logger_name, operation_type):
        """
               Description:
                   Fetches the filter ID from Pipedrive based on certain conditions.

               Args:
                    api_token (str): Pipedrive API token.
                    odoo_id (str): odoo company id store in pipedrive record.
                    field_id (int): ID of the field.
                    type (str): Type of the filter (e.g., "deals").
                    object (str): Type of the object (e.g., "deal").

               Returns:
                   str: Filter ID retrieved from Pipedrive.
               """
        try:
            url = f"{self.__API_BASE_URL}filters?api_token={api_token}"
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

            payload = json.dumps({
                "name": "Filter Record by Update Time",
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
                                    "value": odoo_id,
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

            response = self.fetch_data(url, headers, payload, method="POST")
            # Make a POST request to the API endpoint

            if response.status_code in [200, 201]:
                # Parse the response JSON
                response_json = response.json()
                companies = response_json.get('data', [])
                filter_id = companies['id']
                if filter_id:
                    self.env['opd.filter'].create({'filter_id': str(filter_id)})
                return filter_id
            else:
                self.http_log_error(f"{response.status_code} - {response.reason}", logger_name,
                                    f"Failed to create {logger_name} filter ID", payload, response.text,
                                    'pipedrive', operation_type, odoo_id, f"HTTP {response.status_code}")
                return None
        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching {logger_name} filter ID '
            self.exception_log_error(error_details, logger_name, description, 'pipedrive', operation_type, odoo_id, error_type)
            return None
    # ------------------------------ Get Company Related Contacts From Odoo To Pipedrive ------------------------#
    def odoo_company_related_contacts(self, instance_id, odoo_id,api_token, model_name,contact_model,
         field_model_name,dropdown_field_mapping_name, operation_type):
        """
        Transfer contacts related to a company from Odoo to Pipedrive.

        Args:
            instance_id: The Pipedrive instance ID.
            odoo_id: The ID of the company in Odoo.
            org_id: The ID of the organization in Pipedrive to link the contacts to.
            api_token: The API token for Pipedrive.
            model_name: The name of the Odoo model containing the company data.
            contact_model: The name of the Pipedrive model for contacts.
            field_model_name: The name of the model containing field mappings between Pipedrive and Odoo.
            dropdown_field_mapping_name: The name of the field in `instance_id` containing dropdown mapping information.

        Returns:
            None
        """
        additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'is_company', 'write_date',
                             'parent_id', 'sync_to_pipedrive']
        domain = [
            ('parent_id', '=', odoo_id),
            ('is_company', '=', False),
            ('sync_to_pipedrive', '=', 'yes'),
            ('active', '=', True)
        ]
        contact_records = self.env['opd.mapper.mixin'].fetch_related_odoo_records(field_model_name, model_name,
                          additional_fields, domain,offset=None, limit=None)


        if not contact_records:
            return

        headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

        for contact_record in contact_records:
            # Call the transfer_contact_data method
            result, pipedrive_record_id, org_id, partner_org_id, contact_id, contact_email, dynamic_fields_values_hash = \
                self.env['opd.mapper.mixin'].transfer_contact_data(contact_record, instance_id,
                field_model_name, dropdown_field_mapping_name,contact_model, 'opd.contactmapper', 'people', 'person',
                'contact', operation_type, check_hash=False)

            if result is not None and result != 'no_action' and org_id:
                self.handle_contact_sync(instance_id, contact_record, 'persons', pipedrive_record_id, org_id, headers,
                                         api_token, dynamic_fields_values_hash, operation_type)

    # --------------------------- Sync Contact With Company and Lead or Deal ---------------------------- #

    def handle_contact_sync(self, instance_id, contact_record, pipedrive_model_name, pipedrive_record_id, org_id,
                            headers, api_token, dynamic_fields_values_hash, operation_type):
        """
        Handle the synchronization of a contact record after determining if it needs to be updated or created.

        Args:
            contact_record: The contact record in Odoo.
            pipedrive_record_id: The ID of the contact record in Pipedrive.
            org_id: The ID of the organization in Pipedrive.
            instance_id: The Pipedrive instance ID.
            headers: Headers for the Pipedrive API requests.
            api_token: The API token for Pipedrive.

        Returns:
            None
        """
        response = None
        sync_payload = {}
        if pipedrive_model_name == 'persons':
            sync_payload = {'org_id': int(org_id)}
            update_payload = json.dumps(sync_payload)
            update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_record_id}?api_token={api_token}"
            response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)
        elif pipedrive_model_name == 'leads' or pipedrive_model_name == 'deals':
            sync_payload = {'person_id': int(org_id)}
            update_payload = json.dumps(sync_payload)
            if pipedrive_model_name == 'leads':
                update_endpoint = f"{self.__API_BASE_URL}{pipedrive_model_name}/{pipedrive_record_id}?api_token={api_token}"
                response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)
            else:
                update_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}/{pipedrive_record_id}?api_token={api_token}"
                response = requests.request("PATCH", update_endpoint, headers=headers, data=update_payload)

        record_id = contact_record.get('id') if isinstance(contact_record, dict) else contact_record.id
        if not response or response.status_code != 200:
            error_details = f"{response.status_code} - {response.reason}" if response else _('No response from Pipedrive API')
            description = _('Failed to sync contact')
            self.http_log_error(
                error_details, 'contact', description, sync_payload,
                response.text if response else '', 'pipedrive', operation_type, record_id,
                f"HTTP {response.status_code}" if response else 'HTTP N/A'
            )
        else:
            if pipedrive_model_name == 'persons':
                record = self.env['res.partner'].browse(record_id)
                record.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                record.env.cr.commit()
            else:
                record_type = contact_record.get('type') if isinstance(contact_record,
                                                                       dict) else contact_record.type
                record = self.env['crm.lead'].search(
                    [('id', '=', record_id), ('type', '=', record_type), ('active', '=', True)], limit=1)
                record.write({'pipedrive_id': pipedrive_record_id, 'odoo_hash': dynamic_fields_values_hash})
                record.env.cr.commit()

    # ------------------------------ Get Contact Related Companies From Odoo To Pipedrive ------------------------#

    def odoo_contact_related_companies(self, instance_id, partner_org_id, partner_id,
          api_token, model_name, pipedrive_model_name,field_model_name,dropdown_field_mapping_name, operation_type):

        """
            Fetches companies related to a contact from Odoo and synchronizes them with Pipedrive.

            Args:
                instance_id (Record): The Pipedrive instance to synchronize data with.
                partner_org_id (int): The ID of the organization (company) in Odoo.
                partner_id (int): The ID of the contact (person) in Pipedrive.
                api_token (str): The API token for accessing Pipedrive.
                model_name (str): The name of the Odoo model for the CRM records.
                pipedrive_model_name (str): The name of the model in Pipedrive.
                field_model_name (str): The name of the field model in Odoo for mapping fields.
                dropdown_field_mapping_name (str): The name of the dropdown mapping field.

            Returns:
                None
            """

        # Fetch the company record from Odoo
        try:
            additional_fields = ['user_id', 'odoo_hash', 'pipedrive_id', 'is_company', 'write_date',
                                 'sync_to_pipedrive']
            domain = [
                ('id', '=', partner_org_id),
                ('is_company', '=', True),
                ('sync_to_pipedrive', '=', 'yes'),
                ('active', '=', True)
            ]
            company_record = self.env['opd.mapper.mixin'].fetch_related_odoo_records(field_model_name, model_name,
                                                                                     additional_fields, domain,
                                                                                     offset=None, limit=None)
            if not company_record:
                return
            record_data, dynamic_fields_values_hash, operation_status = self.odoo_to_pipedrive_map_fields(company_record,
            instance_id,field_model_name,dropdown_field_mapping_name,partner_org_id, 'company', operation_type)
            if operation_status == 'skip':
                return
            record_data = self.build_pipedrive_v2_payload(record_data, 'company')

            if record_data:
                # Fetch the filter ID for the company record in Pipedrive
                # odoo_id_value = self.get_odoo_id_field('opd.companymapper', 'odoo_id')
                sync_field = self.get_field_from_mapper('opd.companymapper', 'odoo_id',
                                                        field_name='internal_name')
                # Ensure custom_fields exists
                if "custom_fields" not in record_data or not isinstance(record_data["custom_fields"], dict):
                    record_data["custom_fields"] = {}

                # Merge new value instead of replacing the entire dict
                record_data["custom_fields"][sync_field] = str(partner_org_id)
                company_pipedrive_id = (
                    company_record[0].get('pipedrive_id')
                    if isinstance(company_record, list) and company_record
                    else getattr(company_record, 'pipedrive_id', None)
                )
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}

                if company_pipedrive_id:
                    sync_payload = {'org_id': int(company_pipedrive_id)}
                    payload = json.dumps(sync_payload)
                    update_endpoint = f"{instance_id.api_base_url}/persons/{partner_id}?api_token={api_token}"
                    response = requests.request("PATCH", update_endpoint, headers=headers, data=payload)
                    self.log_operation('company', response.status_code, partner_org_id, payload, 'update', 'pipedrive', operation_type,
                                       'contact', partner_id)
                    if response.status_code != 200:
                        error_details = f"{response.status_code} - {response.reason}"
                        description = f"Failed to update pipedrive company."
                        self.http_log_error(error_details, 'company', description, sync_payload, response.text, 'pipedrive', operation_type,
                                            partner_org_id,f"HTTP {response.status_code}")

                else:
                    # Create a new company record in Pipedrive if it doesn't exist
                    create_endpoint = f"{instance_id.api_base_url}/{pipedrive_model_name}?api_token={api_token}"
                    # Convert the dictionary to JSON format
                    self.env['res.users'].set_record_data(company_record, 'user_id', 'owner_id', record_data)
                    create_payload = json.dumps(record_data)
                    response = self.fetch_data(create_endpoint, headers, create_payload, method="POST")

                    # Check if the response is not successful
                    if response.status_code in [200, 201]:
                        response_json = response.json()
                        record = response_json.get('data', [])
                        pipedrive_id = record.get('id')
                        sync_payload = {}
                        partner = self.env[model_name].browse(partner_org_id)
                        partner.write({'pipedrive_id': pipedrive_id, 'odoo_hash': dynamic_fields_values_hash})
                        partner.env.cr.commit()
                        self.log_operation('company', response.status_code, partner_org_id, record_data, 'create',
                                           'pipedrive', operation_type, 'contact',
                                           partner_id)
                        self.env['res.users'].set_record_data(company_record, 'user_id', 'owner_id', sync_payload)
                        if pipedrive_id:
                            sync_payload['org_id'] = int(pipedrive_id)
                        # Update the contact record in Pipedrive with the related company
                        payload = json.dumps(sync_payload)
                        endpoint = f"{instance_id.api_base_url}/persons/{partner_id}?api_token={api_token}"
                        response = requests.request("PATCH", endpoint, headers=headers, data=payload)
                        if response.status_code != 200:
                            error_details = f"{response.status_code} - {response.reason}"
                            description = f"Failed to update pipedrive company."
                            self.http_log_error(error_details, 'company', description, sync_payload, response.text,
                                                'pipedrive', operation_type, partner_org_id,
                                                f"HTTP {response.status_code}")
                    else:
                        error_details = f"{response.status_code} - {response.reason}"
                        description = f"Failed to create pipedrive company."
                        self.http_log_error(error_details, 'company', description, create_payload, response.text,
                                            'pipedrive', operation_type, partner_org_id, f"HTTP {response.status_code}")

        except Exception as e:
            # create a record in PipedriveLogger to store the error data
            error_details = str(e)
            error_type = 'Exception Error'
            description = f'Error occurred while fetching related company for contact ID {partner_id} from odoo.'
            self.exception_log_error(error_details, 'company', description, 'pipedrive', operation_type, partner_org_id, error_type)
