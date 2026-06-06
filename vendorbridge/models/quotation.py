from odoo import models, fields, api


class VendorBridgeQuotation(models.Model):
    _name = 'vendorbridge.quotation'
    _description = 'Vendor Quotation'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='Quotation Number', readonly=True, copy=False,
        default=lambda self: 'New',
    )
    rfq_id = fields.Many2one(
        'vendorbridge.rfq', string='RFQ', required=True, ondelete='cascade',
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Vendor',
        domain=[('is_vendor', '=', True)], required=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('selected', 'Selected'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        'vendorbridge.quotation.line', 'quotation_id', string='Line Items',
    )
    subtotal = fields.Float(
        string='Subtotal', compute='_compute_amounts', store=True,
    )
    discount_percent = fields.Float(string='Discount %', default=0.0)
    discount_amount = fields.Float(
        string='Discount Amount', compute='_compute_amounts', store=True,
    )
    total = fields.Float(
        string='Total', compute='_compute_amounts', store=True,
    )
    delivery_days = fields.Integer(string='Delivery Days')
    delivery_date = fields.Date(
        string='Expected Delivery', compute='_compute_delivery_date', store=True,
    )
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    is_lowest = fields.Boolean(
        string='Lowest Price', compute='_compute_is_lowest', store=True,
    )
    is_selected = fields.Boolean(string='Selected', default=False)

    @api.depends('line_ids.price_subtotal', 'discount_percent')
    def _compute_amounts(self):
        for quotation in self:
            subtotal = sum(quotation.line_ids.mapped('price_subtotal'))
            quotation.subtotal = subtotal
            quotation.discount_amount = subtotal * (quotation.discount_percent / 100.0)
            quotation.total = subtotal - quotation.discount_amount

    @api.depends('rfq_id.deadline', 'delivery_days')
    def _compute_delivery_date(self):
        for quotation in self:
            if quotation.rfq_id.deadline and quotation.delivery_days:
                from datetime import timedelta
                quotation.delivery_date = quotation.rfq_id.deadline + timedelta(
                    days=quotation.delivery_days
                )
            else:
                quotation.delivery_date = False

    @api.depends('total', 'rfq_id.quotation_ids.total')
    def _compute_is_lowest(self):
        for quotation in self:
            if quotation.rfq_id and quotation.rfq_id.quotation_ids:
                submitted = quotation.rfq_id.quotation_ids.filtered(
                    lambda q: q.state in ('submitted', 'selected')
                )
                if submitted:
                    min_total = min(submitted.mapped('total'))
                    quotation.is_lowest = quotation.total == min_total
                else:
                    quotation.is_lowest = False
            else:
                quotation.is_lowest = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vendorbridge.quotation'
                ) or 'New'
        records = super().create(vals_list)
        return records

    def action_submit(self):
        self.ensure_one()
        self.state = 'submitted'
        # Update RFQ state
        if self.rfq_id.state == 'sent':
            self.rfq_id.state = 'quoted'
        # Notify procurement officer
        template = self.env.ref(
            'vendorbridge.mail_template_quotation_received', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=False)
        self._log_activity(
            'Quotation Submitted',
            f'Quotation {self.name} submitted by {self.vendor_id.name}',
        )

    def action_select(self):
        self.ensure_one()
        # Mark this as selected
        self.is_selected = True
        self.state = 'selected'
        # Reject all other quotations for same RFQ
        siblings = self.rfq_id.quotation_ids.filtered(lambda q: q.id != self.id)
        siblings.write({'state': 'rejected', 'is_selected': False})
        # Update RFQ state
        self.rfq_id.state = 'compared'
        self._log_activity(
            'Quotation Selected',
            f'Quotation {self.name} from {self.vendor_id.name} selected as winner',
        )

    def action_reject(self):
        self.ensure_one()
        self.state = 'rejected'
        self.is_selected = False
        self._log_activity(
            'Quotation Rejected',
            f'Quotation {self.name} from {self.vendor_id.name} rejected',
        )

    def _log_activity(self, action, details=''):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': self._name,
            'record_id': self.id,
            'record_name': self.display_name,
            'action': action,
            'category': 'quotation',
            'user_id': self.env.uid,
            'details': details,
        })
