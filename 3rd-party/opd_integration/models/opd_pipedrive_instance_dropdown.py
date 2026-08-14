# -*- coding: utf-8 -*-
import json

from odoo import models, _
from odoo.exceptions import ValidationError


class PipedriveInstanceDropdownMapping(models.Model):
    _inherit = 'opd.pipedriveinstance'

    def _refresh_dropdown_mapping_notification(self, maps, field_label, odoo_model_label):
        """Build a user notification after refreshing dropdown mappings."""
        message = _(
            'Mapped %(mapped)s of %(total)s %(field)s values using API %(api)s.'
        ) % {
            'mapped': maps.get('mapped_count', maps.get('mapped_stage_count', 0)),
            'total': maps.get('total_count', maps.get('total_pipedrive_stages', 0)),
            'field': field_label,
            'api': maps.get('api_version') or 'unknown',
        }
        notification_type = 'success'
        unmatched = maps.get('unmatched') or maps.get('unmatched_stages') or []
        if unmatched:
            message += ' ' + _(
                'Unmatched Pipedrive values (create matching Odoo %(model)s records with the same name): %(items)s'
            ) % {'model': odoo_model_label, 'items': ', '.join(unmatched)}
            notification_type = 'warning'
        unmatched_pipelines = maps.get('unmatched_pipelines') or []
        if unmatched_pipelines:
            message += ' ' + _(
                'Pipeline mapping is empty for: %(pipelines)s. '
                'Rename each Pipedrive pipeline to match an Odoo Sales Team name exactly '
                '(or use a single pipeline and single sales team for auto-link), then refresh again.'
            ) % {'pipelines': ', '.join(unmatched_pipelines)}
            notification_type = 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dropdown Mapping'),
                'message': message,
                'type': notification_type,
                'sticky': notification_type == 'warning',
            },
        }

    def _merge_dropdown_mapping_fields(self, maps, field_pairs):
        """Merge mapping builder output into instance JSON dropdown fields."""
        for field_name, map_key in field_pairs:
            existing = {}
            raw_mapping = getattr(self, field_name) or ''
            if raw_mapping:
                try:
                    existing = json.loads(raw_mapping)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            existing.update(maps[map_key])
            self.write({field_name: json.dumps(existing, indent=4)})

    def action_refresh_deal_dropdown_mapping(self):
        """Refresh deal stage/pipeline dropdown mappings from Pipedrive."""
        self.ensure_one()
        if not self.is_connected:
            raise ValidationError(_('Connect the Pipedrive instance before refreshing dropdown mappings.'))

        mixin = self.env['opd.mapper.mixin']
        maps = mixin._build_deal_stage_pipeline_dropdown_mapping(self)
        if not maps:
            raise ValidationError(_(
                'Could not fetch stages/pipelines from Pipedrive. '
                'Check the API token and try again.'
            ))

        self._merge_dropdown_mapping_fields(maps, (
            ('pipedrive_deal_dropdown_mapping', 'pipedrive'),
            ('odoo_deal_dropdown_mapping', 'odoo'),
        ))
        return self._refresh_dropdown_mapping_notification(
            maps, _('stage'), _('CRM stages')
        )

    def action_refresh_lead_dropdown_mapping(self):
        """Refresh lead channel / source dropdown mappings from Pipedrive."""
        self.ensure_one()
        if not self.is_connected:
            raise ValidationError(_('Connect the Pipedrive instance before refreshing dropdown mappings.'))

        mixin = self.env['opd.mapper.mixin']
        maps = mixin._build_lead_channel_dropdown_mapping(self)
        if not maps:
            raise ValidationError(_(
                'Could not fetch lead channel options from Pipedrive. '
                'Import Lead Fields or check the API token, then try again.'
            ))

        self._merge_dropdown_mapping_fields(maps, (
            ('pipedrive_lead_dropdown_mapping', 'pipedrive'),
            ('odoo_lead_dropdown_mapping', 'odoo'),
        ))
        return self._refresh_dropdown_mapping_notification(
            maps, _('channel'), _('UTM sources')
        )
