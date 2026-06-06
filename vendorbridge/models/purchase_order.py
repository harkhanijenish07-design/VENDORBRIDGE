from odoo import models, fields, api


class VendorBridgePurchaseOrder(models.Model):
    _name = 'vendorbridge.purchaseorder'
    _description = 'Purchase Order'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='PO Number', readonly=True, copy=False,
        default=lambda self: 'New',
    )
    quotation_id = fields.Many2one(
        'vendorbridge.quotation', string='Quotation', required=True,
    )
    rfq_id = fields.Many2one(
        'vendorbridge.rfq', string='RFQ',
        related='quotation_id.rfq_id', readonly=True, store=True,
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor',
        related='quotation_id.vendor_id', readonly=True, store=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    date_order = fields.Date(
        string='Order Date', default=fields.Date.context_today,
    )
    date_planned = fields.Date(string='Planned Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many(
        'vendorbridge.purchase.order.line', 'order_id', string='Order Lines',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    amount_untaxed = fields.Float(
        string='Untaxed Amount', compute='_compute_amounts', store=True,
    )
    amount_tax = fields.Float(
        string='Tax Amount', compute='_compute_amounts', store=True,
    )
    amount_total = fields.Float(
        string='Total Amount', compute='_compute_amounts', store=True,
    )
    invoice_id = fields.Many2one(
        'vendorbridge.invoice', string='Generated Invoice', readonly=True,
    )
    notes = fields.Text(string='Notes')
    user_id = fields.Many2one(
        'res.users', string='Responsible',
        default=lambda self: self.env.user,
    )

    @api.depends('line_ids.price_subtotal')
    def _compute_amounts(self):
        for order in self:
            amount_untaxed = sum(order.line_ids.mapped('price_subtotal'))
            order.amount_untaxed = amount_untaxed
            # Tax will be computed at invoice level with GST
            order.amount_tax = 0.0
            order.amount_total = amount_untaxed

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vendorbridge.purchaseorder'
                ) or 'New'
        records = super().create(vals_list)
        for record in records:
            record._log_activity(
                'Purchase Order Created',
                f'PO {record.name} created from quotation {record.quotation_id.name}',
            )
        return records

    def action_confirm(self):
        self.ensure_one()
        self.state = 'confirmed'
        # Update vendor total_orders
        if self.vendor_id:
            self.vendor_id._compute_total_orders()
        # Send PO confirmation email to vendor
        template = self.env.ref(
            'vendorbridge.mail_template_po_confirmation', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=False)
        self._log_activity(
            'Purchase Order Confirmed',
            f'PO {self.name} confirmed. Vendor: {self.vendor_id.name}',
        )
        # Auto-create Invoice
        self._create_invoice()

    def action_done(self):
        self.ensure_one()
        self.state = 'done'
        self._log_activity('Purchase Order Completed')

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self._log_activity('Purchase Order Cancelled')

    def _create_invoice(self):
        self.ensure_one()
        default_gst = self.env['ir.config_parameter'].sudo().get_param(
            'vendorbridge.default_gst', '18'
        )
        invoice = self.env['vendorbridge.invoice'].create({
            'purchase_order_id': self.id,
            'company_id': self.company_id.id,
            'gst_rate': default_gst,
            'notes': self.notes,
        })
        # Create invoice lines from PO lines
        for po_line in self.line_ids:
            self.env['vendorbridge.invoice.line'].create({
                'invoice_id': invoice.id,
                'product_id': po_line.product_id.id if po_line.product_id else False,
                'description': po_line.description,
                'quantity': po_line.quantity,
                'uom_id': po_line.uom_id.id if po_line.uom_id else False,
                'price_unit': po_line.price_unit,
            })
        self.invoice_id = invoice.id
        # Update RFQ state
        if self.rfq_id:
            self.rfq_id.state = 'invoiced'

    def _log_activity(self, action, details=''):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': self._name,
            'record_id': self.id,
            'record_name': self.display_name,
            'action': action,
            'category': 'purchase_order',
            'user_id': self.env.uid,
            'details': details,
        })
