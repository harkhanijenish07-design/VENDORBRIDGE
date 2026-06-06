from odoo import models, fields


class VendorBridgeRFQLine(models.Model):
    _name = 'vendorbridge.rfq.line'
    _description = 'RFQ Line Item'

    rfq_id = fields.Many2one(
        'vendorbridge.rfq', string='RFQ', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    note = fields.Text(string='Notes')
