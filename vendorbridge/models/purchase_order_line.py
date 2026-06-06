from odoo import models, fields, api


class VendorBridgePurchaseOrderLine(models.Model):
    _name = 'vendorbridge.purchase.order.line'
    _description = 'Purchase Order Line'

    order_id = fields.Many2one(
        'vendorbridge.purchaseorder', string='Purchase Order',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(
        string='Subtotal', compute='_compute_price_subtotal', store=True,
    )
    state = fields.Selection(related='order_id.state', string='Order Status')

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
