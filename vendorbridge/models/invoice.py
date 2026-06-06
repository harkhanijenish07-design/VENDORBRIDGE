from odoo import models, fields, api

GST_RATES = [
    ('0', '0%'),
    ('5', '5%'),
    ('12', '12%'),
    ('18', '18%'),
    ('28', '28%'),
]


class VendorBridgeInvoice(models.Model):
    _name = 'vendorbridge.invoice'
    _description = 'Invoice'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='Invoice Number', readonly=True, copy=False,
        default=lambda self: 'New',
    )
    purchase_order_id = fields.Many2one(
        'vendorbridge.purchaseorder', string='Purchase Order', required=True,
    )
    rfq_id = fields.Many2one(
        'vendorbridge.rfq', string='RFQ',
        related='purchase_order_id.rfq_id', readonly=True, store=True,
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor',
        related='purchase_order_id.vendor_id', readonly=True, store=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    invoice_date = fields.Date(
        string='Invoice Date', default=fields.Date.context_today,
    )
    due_date = fields.Date(
        string='Due Date', compute='_compute_due_date', store=True,
        readonly=False,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many(
        'vendorbridge.invoice.line', 'invoice_id', string='Invoice Lines',
    )
    gst_type = fields.Selection([
        ('cgst_sgst', 'CGST + SGST'),
        ('igst', 'IGST'),
    ], string='GST Type', compute='_compute_gst_type', store=True)
    gst_rate = fields.Selection(
        GST_RATES, string='GST Rate', default='18',
    )
    cgst_amount = fields.Float(
        string='CGST Amount', compute='_compute_tax', store=True,
    )
    sgst_amount = fields.Float(
        string='SGST Amount', compute='_compute_tax', store=True,
    )
    igst_amount = fields.Float(
        string='IGST Amount', compute='_compute_tax', store=True,
    )
    tax_amount = fields.Float(
        string='Total Tax', compute='_compute_tax', store=True,
    )
    amount_untaxed = fields.Float(
        string='Untaxed Amount', compute='_compute_tax', store=True,
    )
    amount_total = fields.Float(
        string='Total Amount', compute='_compute_tax', store=True,
    )
    email_sent = fields.Boolean(string='Email Sent', default=False, tracking=True)
    pdf_attachment = fields.Binary(string='Invoice PDF', attachment=True)
    notes = fields.Text(string='Notes')
    user_id = fields.Many2one(
        'res.users', string='Responsible',
        default=lambda self: self.env.user,
    )

    @api.depends('invoice_date')
    def _compute_due_date(self):
        from datetime import timedelta
        for invoice in self:
            if invoice.invoice_date:
                invoice.due_date = invoice.invoice_date + timedelta(days=30)
            else:
                invoice.due_date = False

    @api.depends('vendor_id.state_id', 'company_id.state_id')
    def _compute_gst_type(self):
        for invoice in self:
            vendor_state = invoice.vendor_id.state_id
            company_state = invoice.company_id.state_id
            if vendor_state and company_state and vendor_state == company_state:
                invoice.gst_type = 'cgst_sgst'
            else:
                invoice.gst_type = 'igst'

    @api.depends('line_ids.price_subtotal', 'gst_rate', 'gst_type')
    def _compute_tax(self):
        for invoice in self:
            taxable = sum(invoice.line_ids.mapped('price_subtotal'))
            invoice.amount_untaxed = taxable
            rate = int(invoice.gst_rate or '0') / 100.0

            if invoice.gst_type == 'cgst_sgst':
                invoice.cgst_amount = (taxable * rate) / 2
                invoice.sgst_amount = (taxable * rate) / 2
                invoice.igst_amount = 0.0
            else:
                invoice.cgst_amount = 0.0
                invoice.sgst_amount = 0.0
                invoice.igst_amount = taxable * rate

            invoice.tax_amount = (
                invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount
            )
            invoice.amount_total = taxable + invoice.tax_amount

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vendorbridge.invoice'
                ) or 'New'
        records = super().create(vals_list)
        for record in records:
            record._log_activity(
                'Invoice Generated',
                f'Invoice {record.name} generated for PO {record.purchase_order_id.name}',
            )
            # Auto-send email
            record._send_invoice_email()
        return records

    def _send_invoice_email(self):
        self.ensure_one()
        template = self.env.ref(
            'vendorbridge.mail_template_invoice_auto_email', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
            self.email_sent = True
            self.state = 'sent'
            self._log_activity(
                'Invoice Email Sent',
                f'Invoice email sent to {self.vendor_id.name}',
            )

    def action_mark_paid(self):
        self.ensure_one()
        self.state = 'paid'
        # Close the RFQ
        if self.rfq_id:
            self.rfq_id.state = 'closed'
        # Mark PO as done
        if self.purchase_order_id:
            self.purchase_order_id.state = 'done'
        self._log_activity('Invoice Marked as Paid')

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self._log_activity('Invoice Cancelled')

    def action_send_email(self):
        self.ensure_one()
        self._send_invoice_email()

    def _log_activity(self, action, details=''):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': self._name,
            'record_id': self.id,
            'record_name': self.display_name,
            'action': action,
            'category': 'invoice',
            'user_id': self.env.uid,
            'details': details,
        })
