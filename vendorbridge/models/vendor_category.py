from odoo import models, fields, api


class VendorCategory(models.Model):
    _name = 'vendorbridge.vendor.category'
    _description = 'Vendor Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
