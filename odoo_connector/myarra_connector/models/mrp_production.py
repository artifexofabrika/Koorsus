from odoo import models
import requests
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_myarra_param(self, key, default=''):
        """Fetch a config parameter. search() works on all Odoo versions."""
        param = self.env['ir.config_parameter'].sudo().search(
            [('key', '=', key)], limit=1
        )
        return param.value if param else default

    def action_sync_to_myarra(self):
        url = self._get_myarra_param('myarra.api_url')
        token = self._get_myarra_param('myarra.api_token')

        if not url or not token:
            raise models.ValidationError("Please configure Myarra API settings first.")

        jobs = []
        for mo in self:
            part_number = mo.product_id.default_code or 'UNKNOWN'
            jobs.append({
                "job_number": mo.name,
                "part_number": part_number,
                "line_name": "Main Line",
                "target_quantity": int(mo.product_qty),
                "scheduled_start": str(mo.date_start) if mo.date_start else None,
                "scheduled_end": str(mo.date_finished) if mo.date_finished else None,
            })

        headers = {
            'Content-Type': 'application/json',
            'X-Myarra-Token': token,
        }

        try:
            response = requests.post(url, json=jobs, headers=headers, timeout=15)
        except Exception as e:
            raise models.ValidationError(f"Failed to connect to Myarra: {str(e)}")

        if response.status_code != 200:
            raise models.ValidationError(
                f"Myarra returned status {response.status_code}: {response.text}"
            )

        result = response.json()
        msg = f"Synced: {result.get('imported', 0)} jobs."
        if result.get('errors'):
            msg += f" Errors: {result['errors']}"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Myarra Sync',
                'message': msg,
                'type': 'success',
                'sticky': False,
            },
        }