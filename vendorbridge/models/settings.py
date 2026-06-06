from odoo import models, fields

GST_RATES = [
    ('0', '0%'),
    ('5', '5%'),
    ('12', '12%'),
    ('18', '18%'),
    ('28', '28%'),
]


class VendorBridgeSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    threshold_approver_1 = fields.Float(
        string='Threshold for 1 Approver (₹)',
        config_parameter='vendorbridge.threshold_1',
        default=50000.0,
    )
    threshold_approver_2 = fields.Float(
        string='Threshold for 2 Approvers (₹)',
        config_parameter='vendorbridge.threshold_2',
        default=200000.0,
    )
    default_gst_rate = fields.Selection(
        GST_RATES,
        string='Default GST Rate',
        config_parameter='vendorbridge.default_gst',
        default='18',
    )
