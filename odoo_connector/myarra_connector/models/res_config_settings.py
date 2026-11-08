from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    myarra_api_url = fields.Char(string="Myarra API URL", config_parameter='myarra.api_url', default='http://192.168.100.2:5002/api/odoo/jobs')
    myarra_api_token = fields.Char(string="Myarra API Token", config_parameter='myarra.api_token', default='MYARRA-ODOO-SECRET')
