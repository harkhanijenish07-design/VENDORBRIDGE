from odoo import models, fields, api

GST_RATES = [
    ('0', '0%'),
    ('5', '5%'),
    ('12', '12%'),
    ('18', '18%'),
    ('28', '28%'),
]


class VendorBridgeQuotationLine(models.Model):
    _name = 'vendorbridge.quotation.line'
    _description = 'Quotation Line Item'

    quotation_id = fields.Many2one(
        'vendorbridge.quotation', string='Quotation', ondelete='cascade',
    )
    rfq_line_id = fields.Many2one(
        'vendorbridge.rfq.line', string='RFQ Line',
    )
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Float(string='Unit Price')
    gst_rate = fields.Selection(
        GST_RATES, string='GST %', default='18',
    )
    price_subtotal = fields.Float(
        string='Subtotal', compute='_compute_price_subtotal', store=True,
    )
    note = fields.Text(string='Notes')

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.unit_price
