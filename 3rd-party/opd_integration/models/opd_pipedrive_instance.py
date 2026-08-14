from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import ValidationError
import logging
import requests
import json

from .opd_dry_function import PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG


_logger = logging.getLogger(__name__)


class PipedriveInstance(models.Model):
        """
           Represents a Pipedrive Instance in the system, which holds configuration details and synchronization settings
           for various entities like contacts, companies, deals, leads, and products between Odoo and Pipedrive.
        """
        _name = 'opd.pipedriveinstance'
        _description = 'Pipedrive Instance'
        _inherit = ['mail.thread', 'mail.activity.mixin']
        __API_BASE_URL = 'https://api.pipedrive.com/v1/'

        name = fields.Char(default='Pipedrive Instance')
        api_token = fields.Char(string='Pipedrive App Token')
        pagination_size = fields.Integer(string='Pagination Size', required=True, default=25)
        is_default_instance = fields.Boolean(default=False)
        is_connected = fields.Boolean(default=False)
        api_base_url = fields.Char(string='Base URL')

        # ************************************ Scheduler **********************************
        progress_stage = fields.Selection([('not_started', 'Not Started'), ('user_otp', 'User OTP'),
                                           ('user_pto', 'User PTO'), ('account_otp', 'Account OTP'),
                                           ('account_pto', 'Account PTO'), ('contact_otp', 'Contact OTP'),
                                           ('contact_pto', 'Contact PTO'), ('lead_otp', 'Lead OTP'),
                                           ('lead_pto', 'Lead PTO'), ('deal_otp', 'Deal OTP'),
                                           ('deal_pto', 'Deal PTO'), ('product_otp', 'Product OTP'),
                                           ('product_pto', 'Product PTO'), ('completed', 'Completed')
                                           ], string='Progress Stage', default='not_started')

        # ---------------------------------- Company Fields ------------------------------------- #
        is_company_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        odoo_company_last_sync_date = fields.Datetime(tracking=True)
        odoo_company_dropdown_mapping = fields.Text(tracking=True)
        is_company_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        pipedrive_company_last_sync_date = fields.Datetime(tracking=True)
        pipedrive_company_dropdown_mapping = fields.Text(tracking=True)
        companies_line_ids = fields.One2many("pipedriveinstance.companies.lines", "companymapper_id",
                                             string="Companies Lines")
        is_company_notes = fields.Boolean(default=False, string="Notes")
        is_company_emails = fields.Boolean(default=False, string="Emails")
        is_company_tasks = fields.Boolean(default=False, string="Tasks")
        is_company_meetings = fields.Boolean(default=False, string="Meetings")
        is_company_calls = fields.Boolean(default=False, string="Calls")
        is_company_files = fields.Boolean(default=False, string="Files")
        odoo_company_related_leads = fields.Boolean(default=False)
        odoo_company_related_deals = fields.Boolean(default=False)
        odoo_company_related_contacts = fields.Boolean(default=False)
        odoo_company_last_id = fields.Integer(string='Odoo Company Last Id')
        pipedrive_company_last_id = fields.Integer(string='Pipedrive Company Last Id')
        odoo_company_sync_date = fields.Datetime(string='Odoo Company Last Sync Date')
        pipedrive_company_related_leads = fields.Boolean(default=False)
        pipedrive_company_related_deals = fields.Boolean(default=False)
        pipedrive_company_related_contacts = fields.Boolean(default=False)

        # ---------------------------------- Contact Fields ------------------------------------- #
        is_contact_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        odoo_contact_last_sync_date = fields.Datetime(tracking=True)
        odoo_contacts_dropdown_mapping = fields.Text(tracking=True)
        is_contact_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        pipedrive_contact_last_sync_date = fields.Datetime(tracking=True)
        pipedrive_contacts_dropdown_mapping = fields.Text(tracking=True)
        contacts_line_ids = fields.One2many("pipedriveinstance.contacts.lines", "contactmapper_id", string="Contacts Lines")
        is_contact_notes = fields.Boolean(default=False, string="Notes")
        is_contact_emails = fields.Boolean(default=False, string="Emails")
        is_contact_tasks = fields.Boolean(default=False, string="Tasks")
        is_contact_meetings = fields.Boolean(default=False, string="Meetings")
        is_contact_calls = fields.Boolean(default=False, string="Calls")
        is_contact_files = fields.Boolean(default=False, string="Files")
        pipedrive_contact_related_deals = fields.Boolean(default=False)
        pipedrive_contact_related_leads = fields.Boolean(default=False)
        pipedrive_contact_related_companies = fields.Boolean(default=False)
        odoo_contact_related_deals = fields.Boolean(default=False)
        odoo_contact_related_leads = fields.Boolean(default=False)
        odoo_contact_related_companies = fields.Boolean(default=False)
        odoo_contact_last_id = fields.Integer(string='Contact Last Id')
        pipedrive_contact_last_id = fields.Integer(string='Pipedrive Contact Last Id')
        odoo_contact_sync_date = fields.Datetime(string='Odoo Contact Last Sync Date')

        # ---------------------------------- Deal Fields ------------------------------------- #
        is_deal_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        odoo_deal_last_sync_date = fields.Datetime(tracking=True)
        odoo_deal_dropdown_mapping = fields.Text(
            tracking=True,
            help="Read-only in the form view. Auto-built from Pipedrive stages/pipelines. "
                 "Stages map by name then pipeline order; pipelines map when the Pipedrive pipeline name "
                 "matches an Odoo Sales Team name (or one pipeline + one team auto-link).",
        )
        is_deal_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        pipedrive_deal_last_sync_date = fields.Datetime(tracking=True)
        pipedrive_deal_dropdown_mapping = fields.Text(
            tracking=True,
            help="Read-only in the form view. Auto-built from Pipedrive stages/pipelines. "
                 "An empty pipeline_id object means no pipeline name matched an Odoo Sales Team — "
                 "align names and use Refresh Stage & Pipeline Mapping.",
        )
        deals_line_ids = fields.One2many("pipedriveinstance.deals.lines", "dealmapper_id",
                                         string="Leads Lines")
        is_deal_notes = fields.Boolean(default=False, string="Notes")
        is_deal_emails = fields.Boolean(default=False, string="Emails")
        is_deal_tasks = fields.Boolean(default=False, string="Tasks")
        is_deal_meetings = fields.Boolean(default=False, string="Meetings")
        is_deal_calls = fields.Boolean(default=False, string="Calls")
        is_deal_files = fields.Boolean(default=False, string="Files")
        # odoo_deal_related_contacts = fields.Boolean(default=True)
        # odoo_deal_related_companies = fields.Boolean(default=True)
        pipedrive_deal_related_contacts = fields.Boolean(default=False)
        pipedrive_deal_related_companies = fields.Boolean(default=False)
        odoo_deal_last_id = fields.Integer(string='Deal Last Id')
        pipedrive_deal_last_id = fields.Integer(string='Pipedrive Deal Last Id')
        odoo_deal_sync_date = fields.Datetime(string='Odoo Deal Last Sync Date')

        # ---------------------------------- Lead Fields ------------------------------------- #

        is_lead_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        odoo_lead_last_sync_date = fields.Datetime(tracking=True)
        odoo_lead_dropdown_mapping = fields.Text(tracking=True)
        odoo_lead_last_id = fields.Integer(string='Lead Last Id')
        pipedrive_lead_last_id = fields.Char(string='Pipedrive Lead Last Id')
        odoo_lead_sync_date = fields.Datetime(string='Odoo Lead Last Sync Date')
        is_lead_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        pipedrive_lead_last_sync_date = fields.Datetime(tracking=True)
        pipedrive_lead_dropdown_mapping = fields.Text(tracking=True)
        leads_line_ids = fields.One2many("pipedriveinstance.leads.lines", "leadmapper_id",
                                         string="Leads Lines")
        pipedrive_lead_related_contacts = fields.Boolean(default=False)
        pipedrive_lead_related_companies = fields.Boolean(default=False)
        is_lead_notes = fields.Boolean(default=False, string="Notes")
        is_lead_emails = fields.Boolean(default=False, string="Emails")
        is_lead_tasks = fields.Boolean(default=False, string="Tasks")
        is_lead_meetings = fields.Boolean(default=False, string="Meetings")
        is_lead_calls = fields.Boolean(default=False, string="Calls")

        # ---------------------------------- Product Fields ------------------------------------- #

        is_product_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        odoo_product_last_sync_date = fields.Datetime(tracking=True)
        odoo_product_dropdown_mapping = fields.Text(tracking=True)
        is_product_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        pipedrive_product_last_sync_date = fields.Datetime(tracking=True)
        odoo_product_last_id = fields.Integer(string='Product Last Id')
        pipedrive_product_last_id = fields.Integer(string='Pipedrive Product Last Id')
        pipedrive_product_dropdown_mapping = fields.Text(tracking=True)
        products_line_ids = fields.One2many("pipedriveinstance.products.lines", "productmapper_id",
                                            string="Products Lines")

        # ----------------- Sync Related Modules And Activity Fields -------------------- #

        pipedrive_activity_last_sync_date = fields.Datetime(tracking=True)
        odoo_activity_last_sync_date = fields.Datetime(tracking=True)
        is_activity_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        is_activity_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        is_related_module_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        is_related_module_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        odoo_related_modules_last_sync_date = fields.Datetime(tracking=True)
        pipedrive_related_modules_last_sync_date = fields.Datetime(tracking=True)
        odoo_company_sync_last_id = fields.Integer(string='Odoo Sync Company Last ID')
        odoo_contact_sync_last_id = fields.Integer(string='Odoo Sync Contact Last ID')
        odoo_lead_sync_last_id = fields.Integer(string='Odoo Sync Lead Last ID')
        odoo_deal_sync_last_id = fields.Integer(string='Odoo Sync Deal Last ID')
        pipedrive_company_sync_last_id = fields.Integer(string='Pipedrive Sync Company Last ID')
        pipedrive_contact_sync_last_id = fields.Integer(string='Pipedrive Sync Contact Last ID')
        pipedrive_lead_sync_last_id = fields.Integer(string='Pipedrive Sync Lead Last ID')
        pipedrive_deal_sync_last_id = fields.Integer(string='Pipedrive Sync Deal Last ID')

        # ---------------------------------- Users Fields ------------------------------------- #
        pipedrive_users_last_sync_date = fields.Datetime(tracking=True)
        odoo_users_last_sync_date = fields.Datetime(tracking=True)
        is_users_sync_odoo_to_pipedrive = fields.Boolean(tracking=True)
        is_users_sync_pipedrive_to_odoo = fields.Boolean(tracking=True)
        is_current_instance = fields.Boolean('Is Current Instance', default=False)

        # ---------------------------------------------------------------------------------------------------- #

        unique_connected = fields.Char(compute="_compute_unique_connected", store=True)

        # ----------------------------------- Delete Logger Fields --------------------------- #

        remove_log_scheduler = fields.Boolean(tracking=True)
        remove_log_month = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'),
                                             ('7', '7'), ('8', '8'), ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12')],
                                            string='Remove Last Month Log', default='1')

        @api.depends('is_connected')
        def _compute_unique_connected(self):
            for record in self:
                record.unique_connected = 'unique' if record.is_connected else False

        # -------------------------------- Pagination Size Validation --------------------------- #
        @api.constrains('pagination_size')
        def _check_fields(self):
            for record in self:
                if not record.pagination_size:
                    raise ValidationError('Pagination Size cannot be empty.')
                if record.pagination_size < 1 or record.pagination_size > 200:
                    raise ValidationError('Pagination Size must be between 1 and 200.')

        @api.constrains('is_connected')
        def _check_unique_is_connected(self):
            if self.is_connected:
                other_connected = self.env['opd.pipedriveinstance'].search(
                    [('is_connected', '=', True), ('id', '!=', self.id)])
                if other_connected:
                    raise ValidationError("Only one instance can be connected at a time.")

        # ------------------ Cron method that fetch odoo and pipedrive data ------------- #
        def _cron_fetch_pipedrive_and_odoo_entity(self, field):
            """
            Synchronize entities between Pipedrive and Odoo based on configured synchronization settings.

            Args:
                field (str): The field name representing the entity to synchronize (e.g., 'company', 'contact', 'lead', 'deal', etc.).
            """
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            if instance_id and instance_id.is_connected:
                if getattr(instance_id, f'is_{field}_sync_pipedrive_to_odoo', False):
                    getattr(instance_id, f'pipedrive_to_odoo_{field}')(called_by_scheduler=True)
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Error'),
                        'message': _('Instance is not connected. Please check the connection settings.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        # ---------- Scheduled method to fetch activity data from Pipedrive and Odoo -------- #
        def _cron_fetch_pipedrive_and_odoo_activity(self):
            """
                This method runs as a cron job to synchronize activity data between Pipedrive and Odoo.
            """
            self._cron_fetch_pipedrive_and_odoo_entity('activity')

        # ------------------------------- Fetch All Module Data Odoo and Pipedrive Schedular -------------------------- #

        @api.model
        def _cron_fetch_and_store_odoo_pipedrive_records_scheduler(self):
            scheduler = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            if scheduler and scheduler.is_connected:
                scheduler.fetch_schedular_checkboxes()
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Error'),
                        'message': _('Instance is not connected. Please check the connection settings.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        # --------------------------------- Fetch Schedular Checkbox ----------------------------------- #
        def fetch_schedular_checkboxes(self):
            scheduler = self
            if not scheduler.is_connected:
                return

            try:
                # Stage 1: Sync User from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage in ('not_started', 'user_otp'):
                    if scheduler.is_users_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_users(called_by_scheduler=True)
                    scheduler.progress_stage = 'user_pto'
                    scheduler.env.cr.commit()

                # Stage 2: Sync User from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'user_pto':
                    if scheduler.is_users_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_users(called_by_scheduler=True)
                    scheduler.progress_stage = 'account_otp'
                    scheduler.env.cr.commit()

                # Stage 3: Sync Account from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage == 'account_otp':
                    if scheduler.is_company_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_company(called_by_scheduler=True)
                    scheduler.progress_stage = 'account_pto'
                    scheduler.env.cr.commit()

                # Stage 4: Sync Account from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'account_pto':
                    if scheduler.is_company_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_company(called_by_scheduler=True)
                    scheduler.progress_stage = 'contact_otp'
                    scheduler.env.cr.commit()

                # Stage 5: Sync Contact from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage == 'contact_otp':
                    if scheduler.is_contact_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_contact(called_by_scheduler=True)
                    scheduler.progress_stage = 'contact_pto'
                    scheduler.env.cr.commit()

                # Stage 6: Sync Contact from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'contact_pto':
                    if scheduler.is_contact_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_contact(called_by_scheduler=True)
                    scheduler.progress_stage = 'lead_otp'
                    scheduler.env.cr.commit()

                # Stage 7: Sync Lead from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage == 'lead_otp':
                    if scheduler.is_lead_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_lead(called_by_scheduler=True)
                    scheduler.progress_stage = 'lead_pto'
                    scheduler.env.cr.commit()

                # Stage 8: Sync Lead from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'lead_pto':
                    if scheduler.is_lead_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_lead(called_by_scheduler=True)
                    scheduler.progress_stage = 'deal_otp'
                    scheduler.env.cr.commit()

                # Stage 9: Sync Deal from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage == 'deal_otp':
                    if scheduler.is_deal_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_deal(called_by_scheduler=True)
                    scheduler.progress_stage = 'deal_pto'
                    scheduler.env.cr.commit()

                # Stage 10: Sync Deal from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'deal_pto':
                    if scheduler.is_deal_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_deal(called_by_scheduler=True)
                    scheduler.progress_stage = 'product_otp'
                    scheduler.env.cr.commit()

                # Stage 11: Sync Product from Odoo to Pipedrive (OTP)
                if scheduler.progress_stage == 'product_otp':
                    if scheduler.is_product_sync_odoo_to_pipedrive:
                        scheduler.odoo_to_pipedrive_product(called_by_scheduler=True)
                    scheduler.progress_stage = 'product_pto'
                    scheduler.env.cr.commit()

                # Stage 12: Sync Product from Pipedrive to Odoo (PTO)
                if scheduler.progress_stage == 'product_pto':
                    if scheduler.is_product_sync_pipedrive_to_odoo:
                        scheduler.pipedrive_to_odoo_product(called_by_scheduler=True)
                    scheduler.progress_stage = 'completed'
                    scheduler.env.cr.commit()

            except Exception as e:
                error_details = str(e)
                description = _('Error occurred while running scheduler for Odoo and Pipedrive sync.')
                self.env['opd.mapper.mixin'].exception_log_error(
                    error_details, 'schedular', description, 'pipedrive', 'schedular', '', 'Exception Error'
                )

            if scheduler.progress_stage == 'completed':
                scheduler.progress_stage = 'not_started'
                scheduler.env.cr.commit()

        # ------- Toggle the visibility of the 'is_connected' field for records. ------ #

        def toggle_visibility(self):
            """
            Toggle the visibility of the 'is_connected' field for records.

            This method inverts the value of the 'is_connected' field for each record in the recordset.
            If 'is_connected' is True, it will be set to False, and vice versa.

            Usage:
                - Call this method on a recordset to toggle the visibility of the 'is_connected' field.

            """
            for record in self:
                record.is_connected = not record.is_connected

        # --------------------- Test the API connection to Pipedrive ---------------------- #

        def test_connection(self):
            """
            Test the API connection to Pipedrive.

            This method tests the connection to Pipedrive using the provided API token. It attempts to fetch person fields
            from Pipedrive and returns a notification indicating whether the connection was successful or failed.

            Returns:
                dict: An action dictionary for displaying a notification to the user indicating the result of the connection test.

            """

            if not self.is_connected:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _(f'Instance is not connected'),
                        'message': _("The instance is not connected because the 'Is Connected' checkbox is unchecked."),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

            api_token = self.api_token if 'api_token' in self else None

            if not api_token:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('API Token Missing'),
                        'message': _('API Token is not provided.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

            endpoint = f'{self.__API_BASE_URL}personFields?archive=false&api_token={api_token}'
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            payload_rec = ""

            # Make a GET request to the API endpoint
            response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")

            if response.status_code == 200:
                if not (self.api_base_url or '').strip():
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Connection Successful'),
                            'message': _(
                                'API token is valid. Set the Pipedrive API Base URL '
                                '(e.g. https://yourcompany.pipedrive.com/api/v2) before running v2 entity sync.'
                            ),
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Connection set successfully.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': _('Failed to establish connection. Check API Token.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        # --------------------- Test the API connection to sync Pipedrive and Odoo Records ---------------------- #

        def sync_record_test_connection(self, direction, logger_name, current_instance, operation_type):
            """
            Test the API connection to Pipedrive.

            This method tests the connection to Pipedrive using the provided API token. It attempts to fetch person fields
            from Pipedrive and returns a notification indicating whether the connection was successful or failed.

            Returns:
                dict: An action dictionary for displaying a notification to the user indicating the result of the connection test.

            """
            api_token = current_instance.api_token

            if not current_instance.is_connected:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _(f'Instance is not connected'),
                        'message': _("The instance is not connected because the 'Is Connected' checkbox is unchecked."),
                        'type': 'danger',
                        'sticky': False,
                    }
                }, False

            if not api_token:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('API Token Missing'),
                        'message': _('API Token is not provided.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }, False

            endpoint = f'{self.__API_BASE_URL}personFields?archive=false&api_token={api_token}'
            headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {api_token}'}
            payload_rec = ""

            # Make a GET request to the API endpoint
            response = self.env['opd.mapper.mixin'].fetch_data(endpoint, headers, payload_rec, method="GET")
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Connection set successfully.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }, True
            else:
                error_details = f"{response.status_code} - {response.reason}"
                description = f"Failed to complete the operation. Check the API Token or try again."
                self.env['opd.mapper.mixin'].http_log_error(error_details, logger_name, description, payload_rec, response.text,
                                    direction, operation_type, '', f"HTTP {response.status_code}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Failed'),
                        'message': _('Failed to complete the operation. Check the API Token or try again.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }, False

        # -------------- Fetch and synchronize records for Pipedrive and Odoo ---------------- #
        def fetch_records(self, instance_id, last_sync_date, model_name, method_name, scheduler_field_name, operation_type, called_by_scheduler=False):
            """
                Fetch and synchronize records from Pipedrive to Odoo.

                This method fetches records from Pipedrive based on the provided model name and updates the corresponding
                records in Odoo. It calls the specified method on the model to perform the synchronization.

                Args:
                    instance_id (recordset): The Pipedrive instance configuration.
                    last_sync_date (datetime): The date of the last synchronization.
                    model_name (str): The name of the model to fetch records from.
                    method_name (str): The name of the method to call for fetching and updating records.
                    scheduler_field_name (str): The name of the field representing the scheduler checkbox.

                Returns:
                    dict: An action dictionary for displaying a notification to the user if the instance is not connected or
                          if the scheduler is enabled.
            """
            if instance_id.is_connected:
                if not called_by_scheduler and getattr(instance_id, scheduler_field_name):
                    # Scheduler is enabled, show a sticky warning message
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Warning'),
                            'message': _('Scheduler is currently enabled. Manual sync is disabled.'),
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                else:
                    # Proceed with manual synchronization
                    getattr(self.env[model_name], method_name)(instance_id, last_sync_date, operation_type)
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Error'),
                        'message': _('Instance is not connected. Please check the connection settings.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        # ------ """Syncs all relevant data from Pipedrive to Odoo by calling individual sync methods.""" ---- #

        def pipedrive_to_odoo_company(self, called_by_scheduler=False):
            """Receives Companies from Pipedrive"""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            notification, is_connected = self.sync_record_test_connection('odoo', 'company', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.pipedrive_company_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.partner',
                                      'fetch_company_from_pipedrive', 'is_company_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_contact(self, called_by_scheduler=False):
            """Receives Contacts from Pipedrive"""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            notification, is_connected = self.sync_record_test_connection('odoo', 'contact', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            last_sync_date = instance_id.pipedrive_contact_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.partner',
                                      'fetch_contact_from_pipedrive', 'is_contact_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_lead(self, called_by_scheduler=False):
            """Receives Leads from Pipedrive"""
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            notification, is_connected = self.sync_record_test_connection('odoo', 'lead', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.pipedrive_lead_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'crm.lead', 'fetch_lead_from_pipedrive', 'is_lead_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_deal(self, called_by_scheduler=False):
            """Receives Deals from Pipedrive"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('odoo', 'deal', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            last_sync_date = instance_id.pipedrive_deal_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'crm.lead', 'fetch_deal_from_pipedrive', 'is_deal_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_product(self, called_by_scheduler=False):
            """Receives products from Pipedrive"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('odoo', 'product', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            last_sync_date = instance_id.pipedrive_product_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'product.template', 'fetch_product_from_pipedrive', 'is_product_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_activity(self, called_by_scheduler=False):
            """Receives activities from Pipedrive"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('odoo', 'activity', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            last_sync_date = instance_id.pipedrive_activity_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'mail.activity', 'fetch_activity_from_pipedrive', 'is_activity_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        def pipedrive_to_odoo_users(self, called_by_scheduler=False):
            """Receives users from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('odoo', 'user', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.pipedrive_users_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.users', 'fetch_users_from_pipedrive', 'is_users_sync_pipedrive_to_odoo', operation_type, called_by_scheduler)

        # ------ """Syncs all relevant data from Odoo to Pipedrive by calling individual sync methods.""" ------ #

        def odoo_to_pipedrive_company(self, called_by_scheduler=False):
            """Receives companies from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'company', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            last_sync_date = instance_id.odoo_company_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.partner',
                                      'fetch_company_from_odoo', 'is_company_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        def odoo_to_pipedrive_contact(self, called_by_scheduler=False):
            """Receives contacts from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'contact', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.odoo_contact_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.partner',
                                      'fetch_contact_from_odoo', 'is_contact_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        def odoo_to_pipedrive_lead(self, called_by_scheduler=False):
            """Receives leads from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'lead', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.odoo_lead_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'crm.lead',
                                      'fetch_lead_from_odoo', 'is_lead_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        def odoo_to_pipedrive_deal(self, called_by_scheduler=False):
            """Receives deals from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'deal', instance_id, operation_type)
            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.odoo_deal_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'crm.lead',
                                      'fetch_deal_from_odoo', 'is_deal_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        def odoo_to_pipedrive_product(self, called_by_scheduler=False):
            """Receives products from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'product', instance_id, operation_type)

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.odoo_product_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'product.template',
                                      'fetch_product_from_odoo', 'is_product_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        def odoo_to_pipedrive_users(self, called_by_scheduler=False):
            """Receives users from odoo"""
            # Call test_connection to check if the connection is successful
            operation_type = 'manually' if called_by_scheduler is False else 'schedular'
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('pipedrive', 'user', instance_id, operation_type)

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification

            last_sync_date = instance_id.odoo_users_last_sync_date
            return self.fetch_records(instance_id, last_sync_date, 'res.users', 'fetch_users_from_odoo', 'is_users_sync_odoo_to_pipedrive', operation_type, called_by_scheduler)

        # """Import fields for contacts, companies, leads, deals, products, and users from Pipedrive and Odoo.""" #

        def _get_connected_instance_for_custom_fields(self):
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            if not instance_id or not instance_id.is_connected:
                return None, {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Error'),
                        'message': _('Instance is not connected. Please check the connection settings.'),
                        'type': 'danger',
                        'sticky': False,
                    },
                }
            notification, is_connected = self.sync_record_test_connection('', '', instance_id, 'manually')
            if not is_connected:
                return None, notification
            return instance_id, None

        def action_create_required_pipedrive_custom_fields(self):
            """Create sync_to_odoo and odoo_id custom fields on all required Pipedrive entities."""
            instance_id, notification = self._get_connected_instance_for_custom_fields()
            if notification:
                return notification
            result = self.env['opd.mapper.mixin'].ensure_all_pipedrive_required_custom_fields(instance_id)
            return self.env['opd.mapper.mixin'].custom_fields_notification_action(
                result, _('Pipedrive Custom Fields Setup')
            )

        def action_create_required_pipedrive_custom_fields_company(self):
            return self._action_create_required_pipedrive_custom_fields_for_entity('company')

        def action_create_required_pipedrive_custom_fields_contact(self):
            return self._action_create_required_pipedrive_custom_fields_for_entity('contact')

        def action_create_required_pipedrive_custom_fields_lead(self):
            return self._action_create_required_pipedrive_custom_fields_for_entity('lead')

        def action_create_required_pipedrive_custom_fields_deal(self):
            return self._action_create_required_pipedrive_custom_fields_for_entity('deal')

        def action_create_required_pipedrive_custom_fields_product(self):
            return self._action_create_required_pipedrive_custom_fields_for_entity('product')

        def _action_create_required_pipedrive_custom_fields_for_entity(self, entity_key):
            instance_id, notification = self._get_connected_instance_for_custom_fields()
            if notification:
                return notification
            config = PIPEDRIVE_ENTITY_CUSTOM_FIELD_CONFIG.get(entity_key, {})
            result = self.env['opd.mapper.mixin'].ensure_pipedrive_required_custom_fields(instance_id, entity_key)
            return self.env['opd.mapper.mixin'].custom_fields_notification_action(
                result, _('Pipedrive Fields - %s') % config.get('display_name', entity_key)
            )

        def action_import_contacts_fields(self):
            """Import fields for contacts from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful

            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'contact', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            contacts_fields = self.env['opd.contactmapper'].fetch_and_store_contact_fields()
            return self.action_rainbow_effect(contacts_fields, 'Contact')

        def action_import_companies_fields(self):
            """Import fields for companies from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'company', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            companies_fields = self.env['opd.companymapper'].fetch_and_store_company_fields()
            return self.action_rainbow_effect(companies_fields, 'Company')

        def action_import_leads_fields(self):
            """Import fields for leads from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'lead', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            leads_fields = self.env['opd.leadmapper'].fetch_and_store_lead_fields()
            return self.action_rainbow_effect(leads_fields, 'Lead')

        def action_import_deals_fields(self):
            """Import fields for deals from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'deal', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            deals_fields = self.env['opd.dealmapper'].fetch_and_store_deal_fields()
            return self.action_rainbow_effect(deals_fields, 'Deal')

        def action_import_products_fields(self):
            """Import fields for products from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'product', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            products_fields = self.env['opd.productmapper'].fetch_and_store_product_fields()
            return self.action_rainbow_effect(products_fields, 'Product')

        def action_import_activity_fields(self):
            """Import fields for activities from Pipedrive and Odoo."""
            # Call test_connection to check if the connection is successful
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            notification, is_connected = self.sync_record_test_connection('', 'activity', instance_id, 'manually')

            # If the connection failed (is_connected is False), return the notification
            if not is_connected:
                return notification
            activity_fields = self.env['opd.activitymapper'].fetch_and_store_activity_fields()
            return self.action_rainbow_effect(activity_fields, 'Activity')

        # ----- Apply a rainbow effect when importing fields for entities from Pipedrive to Odoo. ------ #
        @api.model
        def action_rainbow_effect(self, arg, name):
            """
                Apply a rainbow effect when importing fields for entities from Pipedrive to Odoo.
                    Args:
                        arg (int): The number of fields successfully imported.
                        name (str): The name of the entity for which fields are imported.
                    create date: 2 April 2024.
                    Returns:
                        dict or None: A dictionary containing the effect parameters if `arg` is truthy,
                                      otherwise returns None.
            """
            if arg:
                return {'effect': {'fadeout': 'slow',
                                   'message': f"{arg} {name} fields stored in odoo successfully",
                                   'type': 'rainbow_man', }}
            return None

        # delete pipedrive filters
        def delete_pipedrive_filters_in_batches(self):
            """
            Deletes Pipedrive filters in batches of 100 at a time.
            After successful deletion, removes those IDs from Odoo model.
            """
            try:
                instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
                # Fetch up to 'batch_size' filters to delete
                filters_to_delete = self.env['opd.filter'].search([], limit=100)
                if not filters_to_delete:
                    _logger.info("No Pipedrive filters found for batch deletion.")
                    return
                pipedrive_token = instance_id.api_token
                # Collect IDs for deletion
                filter_ids = [f.filter_id for f in filters_to_delete if f.filter_id]
                ids_param = ",".join(filter_ids)
                url = f"https://api.pipedrive.com/v1/filters?ids={ids_param}&api_token={pipedrive_token}"
                headers = {'Content-Type': 'application/json', 'Authorization': f'API Key {pipedrive_token}'}

                response = requests.delete(url, headers=headers)
                _logger.info(f"Pipedrive batch delete response: {response.status_code} - {response.text}")

                # On success → remove deleted IDs from Odoo
                if response.status_code in [200, 204]:
                    filters_to_delete.unlink()
                    filters_to_delete.env.cr.commit()
                    _logger.info(f"Successfully deleted {len(filter_ids)} filters from Pipedrive and Odoo.")
                else:
                    _logger.warning(f"Batch deletion failed. Response: {response.text}")

                return response.status_code

            except Exception as e:
                _logger.error(f"Error deleting filters in batch: {e}")
                return None

        # delete filters
        def scheduled_delete_all_instances(self):
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)
            for inst in instance_id:
                inst.delete_pipedrive_filters_in_batches()

        # view schedulers
        def action_view_schedulers(self):
            """Open all schedulers related to this model"""
            return {
                'type': 'ir.actions.act_window',
                'name': _('Schedulers'),
                'res_model': 'ir.cron',
                'view_mode': 'list,form',
                'domain': [('model_id.model', '=', self._name)],
                'target': 'current',
            }

        # pipedrive to odoo sync lead labels
        def sync_lead_labels_from_pipedrive(self):
            instance_id = self.env['opd.pipedriveinstance'].search([('is_connected', '=', True)], limit=1)

            api_token = instance_id.api_token
            url = f"{self.__API_BASE_URL}leadLabels?api_token={api_token}"
            headers = {'Content-Type': 'application/json'}

            response = requests.request("GET", url, headers=headers)

            PIPEDRIVE_TO_ODOO_COLOR = {
                "gray": 0,
                "red": 1,
                "orange": 2,
                "yellow": 3,
                "blue": 8,  # since both 4 and 8 map to blue → choose 4
                "purple": 5,
                "brown": 6,
                "green": 7,  # since both 7 and 10 map to green → choose 7
                "pink": 9,
            }

            if response.status_code != 200:
                return

            response_json = response.json()
            pipedrive_records = response_json.get('data', [])

            for label in pipedrive_records:
                pid = label.get('id')
                name = label.get('name')
                pd_color = label.get("color", "gray")  # Pipedrive color string
                odoo_color = PIPEDRIVE_TO_ODOO_COLOR.get(pd_color, 0)  # default gray

                tag = self.env['crm.tag'].search([
                    '|', ('pipedrive_id', '=', pid), ('name', '=', name)
                ], limit=1)
                if tag:
                    update_payload = { "name": name, "color": odoo_color}
                    tag.write(update_payload)
                    tag.env.cr.commit()
                    self.env['opd.mapper.mixin'].log_operation('lead_label', '', pid, update_payload, 'update', 'odoo',
                                                               'manually', parent_name=None, parent_id=None)
                else:
                    create_payload = {
                        'name': name,
                        "color": odoo_color,
                        'pipedrive_id': pid
                    }
                    label_record = self.env['crm.tag'].create(create_payload)
                    label_record.env.cr.commit()
                    self.env['opd.mapper.mixin'].log_operation('lead_label', '', pid, create_payload, 'create', 'odoo',
                    'manually', parent_name=None,parent_id=None)

        # odoo to pipedrive sync lead labels
        def sync_lead_labels_to_pipedrive(self):
            """
            Sync Odoo CRM Tags → Pipedrive Lead Labels (v1 API).
            Creates + Updates + stores pipedrive_id back to Odoo.
            """
            odoo_record_id = None
            try:
                instance_id = self.search([('is_connected', '=', True)], limit=1)
                if not instance_id:
                    return

                api_token = instance_id.api_token
                base_url = f"{self.__API_BASE_URL}leadLabels?api_token={api_token}"
                headers = {'Content-Type': 'application/json'}

                # Fetch all CRM Tags that are allowed to sync
                odoo_tags = self.env['crm.tag'].search([])
                for tag in odoo_tags:
                    name = tag.name
                    tag_pipedrive_id = tag.pipedrive_id
                    odoo_record_id = tag.id

                    ODOO_TO_PIPEDRIVE_COLOR = {
                        0: "gray",
                        1: "red",
                        2: "orange",
                        3: "yellow",
                        8: "blue",
                        5: "purple",
                        6: "brown",
                        7: "green",
                        9: "pink",
                        4: "blue",
                    }

                    color_name = ODOO_TO_PIPEDRIVE_COLOR.get(tag.color, "gray")

                    # ----------------- PAYLOAD ----------------- #
                    payload = {
                        "name": name,
                        "color": color_name,
                    }


                    # Convert payload to JSON
                    json_payload = json.dumps(payload)
                    # ----------------- UPDATE CASE ----------------- #
                    if tag_pipedrive_id:
                        endpoint = f"{self.__API_BASE_URL}leadLabels/{tag_pipedrive_id}?api_token={api_token}"
                        response = requests.patch(endpoint, data=json_payload, headers=headers)

                        if response.status_code in (200, 201):
                            # log update
                            self.env['opd.mapper.mixin'].log_operation('lead_label', response.status_code, odoo_record_id, payload,
                            'update','pipedrive', 'manually',parent_name=None, parent_id=None)
                        else:
                            # if PD deleted the label, re-create it
                            tag.pipedrive_id = False
                            tag.env.cr.commit()

                    # ----------------- CREATE CASE ----------------- #
                    if not tag.pipedrive_id:
                        create_endpoint = base_url
                        response = requests.post(create_endpoint, data=json_payload, headers=headers)
                        if response.status_code in (200, 201):
                            response_json = response.json()
                            pd_id = response_json.get('data', {}).get('id')

                            if pd_id:
                                tag.write({'pipedrive_id': pd_id})
                                tag.env.cr.commit()
                                self.env['opd.mapper.mixin'].log_operation('lead_label', response.status_code, odoo_record_id, payload,
                                                   'create', 'pipedrive', 'manually', parent_name=None, parent_id=None)
                        else:
                            # log error
                            error_details = f"{response.status_code} - {response.reason}"
                            description = f'lead labels send odoo to pipedrive'
                            self.env['opd.mapper.mixin'].http_log_error(error_details, 'lead_label', description, payload, response.text,
                                                'pipedrive', 'manually', odoo_record_id, f"HTTP {response.status_code}")


            except Exception as e:
                error_details = str(e)
                error_type = 'Exception Error'
                description = f'Error occurred while sync lead labels odoo to pipedrive'
                self.env['opd.mapper.mixin'].exception_log_error(error_details, 'lead_label', description, 'pipedrive', 'manually', odoo_record_id,
                                         error_type)


# ---- """A mixin providing methods to compute Odoo and Pipedrive fields for various entities.""" ----- #

class FieldLinesMixin(models.Model):
    _name = "opd.fieldlinesmixin"
    _description = "Pipedrive Instances Field Lines Mixin"

    @api.depends('odoo_fields_record')
    def _compute_odoo_fields(self):
        for record in self:
            record.odoo_fields = record.odoo_fields_record.display_name if record.odoo_fields_record else ''

    @api.depends('pipedrive_fields_record')
    def _compute_pipedrive_fields(self):
        for record in self:
            record.pipedrive_fields = record.pipedrive_fields_record.display_name if record.pipedrive_fields_record else ''


# ------------------------------------ Contact Mapping ------------------------------------ #

class PipedriveinstancesContactsLines(FieldLinesMixin, models.Model):
    """Represents lines associated with Pipedrive instances for contacts."""
    _name = "pipedriveinstance.contacts.lines"
    _description = "pipedrive Instances Contacts Lines"

    odoo_fields = fields.Char(string='Odoo Fields', compute='_compute_odoo_fields', store=True)
    odoo_fields_type = fields.Char(string='Odoo Fields Type', related='odoo_fields_record.field_type', store=True)
    odoo_fields_record = fields.Many2one('opd.contactmapper', domain=[('system_name', '=', 'Odoo')],
                                         string='Odoo Fields Record')

    pipedrive_fields = fields.Char(string='Pipedrive Fields', compute='_compute_pipedrive_fields', store=True)
    pipedrive_fields_type = fields.Char(string='Pipedrive Fields Type', related='pipedrive_fields_record.field_type',
                                        store=True)
    pipedrive_fields_record = fields.Many2one('opd.contactmapper', domain=[('system_name', '=', 'pipedrive')],
                                              string='Pipedrive Fields Record', required=True)

    description = fields.Char(string='Description')
    contactmapper_id = fields.Many2one("opd.pipedriveinstance", string="Contact Mapper Lines")


# ------------------------------------ Companies Mapping ------------------------------------ #

class PipedriveinstancesCompaniesLines(FieldLinesMixin, models.Model):
    """Represents lines associated with Pipedrive instances for companies."""
    _name = "pipedriveinstance.companies.lines"
    _description = "pipedrive Instances Companies Lines"

    odoo_fields = fields.Char(string='Odoo Fields', compute='_compute_odoo_fields', store=True)
    odoo_fields_type = fields.Char(string='Odoo Fields Type', related='odoo_fields_record.field_type', store=True)
    odoo_fields_record = fields.Many2one('opd.companymapper', domain=[('system_name', '=', 'Odoo')], string='Odoo Fields Record')

    pipedrive_fields = fields.Char(string='Pipedrive Fields', compute='_compute_pipedrive_fields', store=True)
    pipedrive_fields_type = fields.Char(string='Pipedrive Fields Type', related='pipedrive_fields_record'
                                                                                '.field_type',
                                        store=True)
    pipedrive_fields_record = fields.Many2one('opd.companymapper', domain=[('system_name', '=', 'pipedrive')], string='Pipedrive Fields Record', required=True)
    description = fields.Char(string='Description')
    companymapper_id = fields.Many2one("opd.pipedriveinstance", string="Companies Mapper Lines")


# ------------------------------------ Leads Mapping ------------------------------------ #

class PipedriveinstancesLeadsLines(FieldLinesMixin, models.Model):
    """Represents lines associated with Pipedrive instances for leads."""
    _name = "pipedriveinstance.leads.lines"
    _description = "pipedrive Instances Leads Lines"

    odoo_fields = fields.Char(string='Odoo Fields', compute='_compute_odoo_fields', store=True)
    odoo_fields_type = fields.Char(string='Odoo Fields Type', related='odoo_fields_record.field_type', store=True)
    odoo_fields_record = fields.Many2one('opd.leadmapper', domain=[('system_name', '=', 'Odoo')],
                                         string='Odoo Fields Record')

    pipedrive_fields = fields.Char(string='Pipedrive Fields', compute='_compute_pipedrive_fields', store=True)
    pipedrive_fields_type = fields.Char(string='Pipedrive Fields Type', related='pipedrive_fields_record.field_type',
                                        store=True)
    pipedrive_fields_record = fields.Many2one('opd.leadmapper', domain=[('system_name', '=', 'pipedrive')],
                                              string='Pipedrive Fields Record', required=True)

    description = fields.Char(string='Description')
    leadmapper_id = fields.Many2one("opd.pipedriveinstance", string="Lead Mapper Lines")


# ------------------------------------ Deal Mapping ------------------------------------ #

class PipedriveinstancesDealLines(FieldLinesMixin, models.Model):
    """Represents lines associated with Pipedrive instances for deals."""
    _name = "pipedriveinstance.deals.lines"
    _description = "pipedrive Instances Deals Lines"

    odoo_fields = fields.Char(string='Odoo Fields', compute='_compute_odoo_fields', store=True)
    odoo_fields_type = fields.Char(string='Odoo Fields Type', related='odoo_fields_record.field_type', store=True)
    odoo_fields_record = fields.Many2one('opd.dealmapper', domain=[('system_name', '=', 'Odoo')],
                                         string='Odoo Fields Record')

    pipedrive_fields = fields.Char(string='Pipedrive Fields', compute='_compute_pipedrive_fields', store=True)
    pipedrive_fields_type = fields.Char(string='Pipedrive Fields Type', related='pipedrive_fields_record.field_type',
                                        store=True)
    pipedrive_fields_record = fields.Many2one('opd.dealmapper', domain=[('system_name', '=', 'pipedrive')],
                                              string='Pipedrive Fields Record', required=True)

    description = fields.Char(string='Description')
    dealmapper_id = fields.Many2one("opd.pipedriveinstance", string="Deal Mapper Lines")


# ------------------------------------ Product Mapping ------------------------------------ #

class PipedriveinstancesProductLines(FieldLinesMixin, models.Model):
    """Represents lines associated with Pipedrive instances for products."""
    _name = "pipedriveinstance.products.lines"
    _description = "pipedrive Instances Products Lines"

    odoo_fields = fields.Char(string='Odoo Fields', compute='_compute_odoo_fields', store=True)
    odoo_fields_record = fields.Many2one('opd.productmapper', domain=[('system_name', '=', 'Odoo')],
                                         string='Odoo Fields Record')
    odoo_fields_type = fields.Char(string='Odoo Fields Type', related='odoo_fields_record.field_type', store=True)
    pipedrive_fields = fields.Char(string='Pipedrive Fields', compute='_compute_pipedrive_fields', store=True)
    pipedrive_fields_record = fields.Many2one('opd.productmapper', domain=[('system_name', '=', 'pipedrive')],
                                              string='Pipedrive Fields Record', required=True)
    pipedrive_fields_type = fields.Char(string='Pipedrive Fields Type', related='pipedrive_fields_record.field_type',
                                        store=True)

    description = fields.Char(string='Description')
    productmapper_id = fields.Many2one("opd.pipedriveinstance", string="Product Mapper Lines")
