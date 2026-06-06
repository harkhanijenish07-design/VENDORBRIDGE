from odoo import models, fields, api


class VendorBridgeActivityLog(models.Model):
    _name = 'vendorbridge.activitylog'
    _description = 'Activity Log'
    _order = 'create_date desc'

    name = fields.Char(string='Summary', compute='_compute_name', store=True)
    model_name = fields.Char(string='Model', required=True)
    record_id = fields.Integer(string='Record ID', required=True)
    record_name = fields.Char(string='Record Name')
    action = fields.Char(string='Action', required=True)
    category = fields.Selection([
        ('rfq', 'RFQ'),
        ('quotation', 'Quotation'),
        ('approval', 'Approval'),
        ('invoice', 'Invoice'),
        ('vendor', 'Vendor'),
        ('purchase_order', 'Purchase Order'),
    ], string='Category')
    user_id = fields.Many2one('res.users', string='User')
    details = fields.Text(string='Details')

    @api.depends('record_name', 'action')
    def _compute_name(self):
        for log in self:
            log.name = f'{log.record_name or ""} - {log.action or ""}'

