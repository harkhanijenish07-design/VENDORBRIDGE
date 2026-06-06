from odoo import models, fields, api
from odoo.exceptions import UserError


class VendorBridgeApprovalWorkflow(models.Model):
    _name = 'vendorbridge.approval.workflow'
    _description = 'Approval Workflow'
    _order = 'approver_level, create_date'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
    )
    rfq_id = fields.Many2one(
        'vendorbridge.rfq', string='RFQ', required=True,
    )
    quotation_id = fields.Many2one(
        'vendorbridge.quotation', string='Quotation', required=True,
    )
    approver_id = fields.Many2one(
        'res.users', string='Approver', required=True,
    )
    approver_level = fields.Integer(string='Approval Level', default=1)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', tracking=True)
    remarks = fields.Text(string='Remarks')
    action_date = fields.Datetime(string='Action Date')

    @api.depends('rfq_id.name', 'approver_id.name', 'approver_level')
    def _compute_name(self):
        for approval in self:
            rfq_name = approval.rfq_id.name or ''
            approver_name = approval.approver_id.name or ''
            approval.name = f'{rfq_name} - Level {approval.approver_level} - {approver_name}'

    def action_approve(self):
        self.ensure_one()
        self.state = 'approved'
        self.action_date = fields.Datetime.now()
        self._log_activity(
            f'Approved by {self.approver_id.name}',
            f'Level {self.approver_level} approval. Remarks: {self.remarks or "None"}',
        )
        # Check if all approvals are done
        rfq = self.rfq_id
        all_approvals = rfq.approval_ids
        approved_count = len(all_approvals.filtered(lambda a: a.state == 'approved'))
        if approved_count >= rfq.approval_required:
            rfq.state = 'approved'
            rfq._log_activity('RFQ Fully Approved', 'All required approvals received.')
            # Auto-create Purchase Order
            self._create_purchase_order()
        else:
            # Notify next approver
            next_approvals = all_approvals.filtered(
                lambda a: a.state == 'pending' and a.approver_level > self.approver_level
            )
            if next_approvals:
                template = self.env.ref(
                    'vendorbridge.mail_template_approval_request',
                    raise_if_not_found=False,
                )
                if template:
                    template.send_mail(rfq.id, force_send=False)

    def action_reject(self):
        self.ensure_one()
        if not self.remarks:
            raise UserError('Remarks are mandatory when rejecting.')
        self.state = 'rejected'
        self.action_date = fields.Datetime.now()
        # Cancel the RFQ
        self.rfq_id.state = 'cancelled'
        self._log_activity(
            f'Rejected by {self.approver_id.name}',
            f'Level {self.approver_level} rejection. Remarks: {self.remarks}',
        )
        self.rfq_id._log_activity(
            'RFQ Cancelled (Approval Rejected)',
            f'Rejected by {self.approver_id.name}: {self.remarks}',
        )

    def _create_purchase_order(self):
        rfq = self.rfq_id
        selected_quotation = rfq.quotation_ids.filtered(lambda q: q.is_selected)
        if not selected_quotation:
            return
        selected_quotation = selected_quotation[0]
        po = self.env['vendorbridge.purchaseorder'].create({
            'quotation_id': selected_quotation.id,
            'company_id': rfq.company_id.id,
            'date_planned': selected_quotation.delivery_date or rfq.deadline,
            'currency_id': selected_quotation.currency_id.id,
            'notes': selected_quotation.notes,
        })
        # Create PO lines from quotation lines
        for q_line in selected_quotation.line_ids:
            self.env['vendorbridge.purchase.order.line'].create({
                'order_id': po.id,
                'product_id': q_line.rfq_line_id.product_id.id if q_line.rfq_line_id and q_line.rfq_line_id.product_id else False,
                'description': q_line.description,
                'quantity': q_line.quantity,
                'uom_id': q_line.rfq_line_id.uom_id.id if q_line.rfq_line_id and q_line.rfq_line_id.uom_id else False,
                'price_unit': q_line.unit_price,
            })
        rfq.state = 'po_created'

    def _log_activity(self, action, details=''):
        self.env['vendorbridge.activitylog'].sudo().create({
            'model_name': self._name,
            'record_id': self.id,
            'record_name': self.display_name,
            'action': action,
            'category': 'approval',
            'user_id': self.env.uid,
            'details': details,
        })
