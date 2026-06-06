import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError

# Indian GSTIN format: 2-digit state code + 10-char PAN + entity number + Z + check digit
GSTIN_REGEX = re.compile(
    r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vendor = fields.Boolean(string='Is Vendor', default=False)
    gst_number = fields.Char(string='GSTIN', size=15)

    @api.constrains('gst_number')
    def _check_gst_number(self):
        """Validate GSTIN format using Indian GST structural rules."""
        for partner in self:
            if partner.gst_number:
                gstin = partner.gst_number.strip().upper()
                if len(gstin) != 15:
                    raise ValidationError(
                        'GSTIN must be exactly 15 characters long. '
                        f'Got {len(gstin)} characters.'
                    )
                if not GSTIN_REGEX.match(gstin):
                    raise ValidationError(
                        f'Invalid GSTIN format: "{gstin}". '
                        'Expected format: 2-digit state code (01-37) + '
                        '10-character PAN + entity number + Z + check digit. '
                        'Example: 27AABCU9603R1ZM'
                    )
    vendor_category_id = fields.Many2one(
        'vendorbridge.vendor.category',
        string='Vendor Category',
    )
    vendor_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('blocked', 'Blocked'),
    ], string='Vendor Status', default='draft', tracking=True)
    vendor_rating = fields.Float(
        string='Rating (0-5)', digits=(2, 1), default=0.0,
    )
    total_orders = fields.Integer(
        string='Total Orders', compute='_compute_total_orders', store=True,
    )
    bank_name = fields.Char(string='Bank Name')
    bank_account_number = fields.Char(string='Bank Account Number')
    ifsc_code = fields.Char(string='IFSC Code', size=11)

    @api.depends('is_vendor')
    def _compute_total_orders(self):
        PO = self.env['vendorbridge.purchaseorder']
        for partner in self:
            if partner.is_vendor:
                partner.total_orders = PO.search_count([
                    ('vendor_id', '=', partner.id),
                    ('state', 'in', ['confirmed', 'done']),
                ])
            else:
                partner.total_orders = 0

    def action_approve_vendor(self):
        for partner in self:
            partner.vendor_status = 'approved'
            self._log_vendor_activity(partner, 'Vendor Approved')
            # Send approval email
            template = self.env.ref(
                'vendorbridge.mail_template_vendor_approved', raise_if_not_found=False
            )
            if template:
                template.send_mail(partner.id, force_send=True)

    def action_reject_vendor(self):
        for partner in self:
            partner.vendor_status = 'rejected'
            self._log_vendor_activity(partner, 'Vendor Rejected')
            template = self.env.ref(
                'vendorbridge.mail_template_vendor_rejected', raise_if_not_found=False
            )
            if template:
                template.send_mail(partner.id, force_send=True)

    def action_block_vendor(self):
        for partner in self:
            partner.vendor_status = 'blocked'
            self._log_vendor_activity(partner, 'Vendor Blocked')

    def _log_vendor_activity(self, partner, action):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': 'res.partner',
            'record_id': partner.id,
            'record_name': partner.display_name,
            'action': action,
            'category': 'vendor',
            'user_id': self.env.uid,
            'details': f'{action}: {partner.name}',
        })
