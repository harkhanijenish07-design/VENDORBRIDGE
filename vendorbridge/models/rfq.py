from odoo import models, fields, api
from odoo.exceptions import UserError


class VendorBridgeRFQ(models.Model):
    _name = 'vendorbridge.rfq'
    _description = 'Request for Quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='RFQ Number', readonly=True, copy=False,
        default=lambda self: 'New',
    )
    title = fields.Char(string='Title', required=True, tracking=True)
    description = fields.Text(string='Description')
    category_id = fields.Many2one(
        'vendorbridge.vendor.category', string='Category',
    )
    requestor_id = fields.Many2one(
        'res.users', string='Requestor',
        default=lambda self: self.env.user, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )
    vendor_ids = fields.Many2many(
        'res.partner', string='Invited Vendors',
        domain=[('is_vendor', '=', True), ('vendor_status', '=', 'approved')],
    )
    deadline = fields.Date(string='Deadline', required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', default='normal', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent to Vendors'),
        ('quoted', 'Quotations Received'),
        ('compared', 'Compared'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('po_created', 'PO Created'),
        ('invoiced', 'Invoiced'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    line_ids = fields.One2many(
        'vendorbridge.rfq.line', 'rfq_id', string='Line Items',
    )
    quotation_ids = fields.One2many(
        'vendorbridge.quotation', 'rfq_id', string='Quotations',
    )
    total_estimated = fields.Float(
        string='Estimated Total', compute='_compute_total_estimated', store=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
    )
    approval_required = fields.Integer(
        string='Approvals Required', compute='_compute_approval_required',
    )
    approval_done = fields.Integer(
        string='Approvals Done', compute='_compute_approval_done', store=True,
    )
    approval_ids = fields.One2many(
        'vendorbridge.approval.workflow', 'rfq_id', string='Approvals',
    )
    quotation_count = fields.Integer(
        compute='_compute_quotation_count', string='Quotation Count',
    )

    @api.depends('quotation_ids.total')
    def _compute_total_estimated(self):
        for rfq in self:
            selected = rfq.quotation_ids.filtered(lambda q: q.is_selected)
            if selected:
                rfq.total_estimated = selected[0].total
            elif rfq.quotation_ids:
                rfq.total_estimated = min(rfq.quotation_ids.mapped('total'))
            else:
                rfq.total_estimated = 0.0

    def _compute_approval_required(self):
        threshold_1 = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'vendorbridge.threshold_1', '50000'
            )
        )
        threshold_2 = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'vendorbridge.threshold_2', '200000'
            )
        )
        for rfq in self:
            total = rfq.total_estimated
            if total < threshold_1:
                rfq.approval_required = 1
            elif total < threshold_2:
                rfq.approval_required = 2
            else:
                rfq.approval_required = 2

    @api.depends('approval_ids.state')
    def _compute_approval_done(self):
        for rfq in self:
            rfq.approval_done = len(
                rfq.approval_ids.filtered(lambda a: a.state == 'approved')
            )

    def _compute_quotation_count(self):
        for rfq in self:
            rfq.quotation_count = len(rfq.quotation_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vendorbridge.rfq'
                ) or 'New'
        records = super().create(vals_list)
        for record in records:
            record._log_activity('RFQ Created', f'RFQ {record.name} created by {record.requestor_id.name}')
        return records

    def action_send_to_vendors(self):
        self.ensure_one()
        if not self.vendor_ids:
            raise UserError('Please select at least one vendor to invite.')
        if not self.line_ids:
            raise UserError('Please add at least one line item.')
        self.state = 'sent'
        # Send email notification to each vendor
        template = self.env.ref(
            'vendorbridge.mail_template_rfq_invitation', raise_if_not_found=False
        )
        if template:
            for vendor in self.vendor_ids:
                template.send_mail(self.id, force_send=False,
                                   email_values={'email_to': vendor.email})
        self._log_activity(
            'RFQ Sent to Vendors',
            f'Sent to: {", ".join(self.vendor_ids.mapped("name"))}',
        )

    def action_initiate_approval(self):
        self.ensure_one()
        selected = self.quotation_ids.filtered(lambda q: q.is_selected)
        if not selected:
            raise UserError('Please select a winning quotation first.')
        self.state = 'pending_approval'
        # Create approval workflow records
        manager_group = self.env.ref('vendorbridge.group_manager', raise_if_not_found=False)
        if not manager_group:
            raise UserError(
                'Manager security group not found. '
                'Please ensure the VendorBridge module is properly installed.'
            )
        managers = self.env['res.users'].search([
            ('groups_id', 'in', manager_group.id),
        ], limit=self.approval_required)
        if not managers:
            raise UserError(
                'No users found in the Manager/Approver group. '
                'Please assign at least one user to the "VendorBridge Manager" '
                'group before initiating approvals.'
            )
        level = 1
        for manager in managers:
            self.env['vendorbridge.approval.workflow'].create({
                'rfq_id': self.id,
                'quotation_id': selected[0].id,
                'approver_id': manager.id,
                'approver_level': level,
                'state': 'pending',
            })
            level += 1
        # Send approval request email
        template = self.env.ref(
            'vendorbridge.mail_template_approval_request', raise_if_not_found=False
        )
        if template:
            first_approver = self.approval_ids.filtered(
                lambda a: a.approver_level == 1
            )
            if first_approver:
                template.send_mail(self.id, force_send=False)
        self._log_activity(
            'Approval Workflow Initiated',
            f'Approvals required: {self.approval_required}',
        )

    def action_cancel(self):
        self.ensure_one()
        self.state = 'cancelled'
        self._log_activity('RFQ Cancelled')

    def action_reset_draft(self):
        self.ensure_one()
        self.state = 'draft'
        self._log_activity('RFQ Reset to Draft')

    def action_view_quotations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quotations',
            'res_model': 'vendorbridge.quotation',
            'view_mode': 'tree,form',
            'domain': [('rfq_id', '=', self.id)],
            'context': {'default_rfq_id': self.id},
        }

    def _log_activity(self, action, details=''):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': self._name,
            'record_id': self.id,
            'record_name': self.display_name,
            'action': action,
            'category': 'rfq',
            'user_id': self.env.uid,
            'details': details,
        })

    def _get_log_category(self):
        return 'rfq'
