from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRFQWorkflow(TransactionCase):
    """Test RFQ creation, threshold evaluation, and approval chain."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rfq_model = cls.env['vendorbridge.rfq']
        cls.category = cls.env['vendorbridge.vendor.category'].create({
            'name': 'IT Hardware',
        })

        # Create approved vendors
        cls.vendor_1 = cls.env['res.partner'].create({
            'name': 'Vendor Alpha',
            'email': 'alpha@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
            'vendor_category_id': cls.category.id,
        })
        cls.vendor_2 = cls.env['res.partner'].create({
            'name': 'Vendor Beta',
            'email': 'beta@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
            'vendor_category_id': cls.category.id,
        })

        # Set threshold parameters
        cls.env['ir.config_parameter'].sudo().set_param(
            'vendorbridge.threshold_1', '50000'
        )
        cls.env['ir.config_parameter'].sudo().set_param(
            'vendorbridge.threshold_2', '200000'
        )

        # Create a manager user for approval tests
        cls.manager_group = cls.env.ref(
            'vendorbridge.group_manager', raise_if_not_found=False
        )

    def _create_rfq(self, title='Test RFQ', **kwargs):
        """Helper to create an RFQ with a line item."""
        vals = {
            'title': title,
            'description': 'Test RFQ description',
            'category_id': self.category.id,
            'deadline': '2026-12-31',
            'priority': 'normal',
            'vendor_ids': [(6, 0, [self.vendor_1.id, self.vendor_2.id])],
        }
        vals.update(kwargs)
        rfq = self.rfq_model.create(vals)
        # Add a line item
        self.env['vendorbridge.rfq.line'].create({
            'rfq_id': rfq.id,
            'description': 'Test Item',
            'quantity': 10.0,
        })
        return rfq

    # ------------------------------------------------------------------
    # RFQ Creation Tests
    # ------------------------------------------------------------------

    def test_rfq_auto_sequence(self):
        """RFQ should get an auto-generated sequence number on creation."""
        rfq = self._create_rfq()
        self.assertNotEqual(rfq.name, 'New',
                            'RFQ name should be auto-generated, not "New"')

    def test_rfq_initial_state_is_draft(self):
        """Newly created RFQ should be in 'draft' state."""
        rfq = self._create_rfq()
        self.assertEqual(rfq.state, 'draft')

    def test_rfq_creation_logs_activity(self):
        """Creating an RFQ should produce an activity log entry."""
        rfq = self._create_rfq(title='Log Test RFQ')
        log = self.env['vendorbridge.activitylog'].search([
            ('model_name', '=', 'vendorbridge.rfq'),
            ('record_id', '=', rfq.id),
            ('action', '=', 'RFQ Created'),
        ])
        self.assertTrue(log, 'Activity log should be created on RFQ creation')

    # ------------------------------------------------------------------
    # Send to Vendors Tests
    # ------------------------------------------------------------------

    def test_send_without_vendors_raises_error(self):
        """Sending an RFQ with no vendors should raise UserError."""
        rfq = self._create_rfq()
        rfq.vendor_ids = [(5, 0, 0)]  # Clear vendors
        with self.assertRaises(UserError):
            rfq.action_send_to_vendors()

    def test_send_without_lines_raises_error(self):
        """Sending an RFQ with no line items should raise UserError."""
        rfq = self._create_rfq()
        rfq.line_ids.unlink()
        with self.assertRaises(UserError):
            rfq.action_send_to_vendors()

    def test_send_changes_state_to_sent(self):
        """Sending an RFQ should change state to 'sent'."""
        rfq = self._create_rfq()
        rfq.action_send_to_vendors()
        self.assertEqual(rfq.state, 'sent')

    # ------------------------------------------------------------------
    # Threshold Evaluation Tests
    # ------------------------------------------------------------------

    def test_threshold_below_50k_requires_1_approver(self):
        """Total below threshold_1 (50k) should require 1 approver."""
        rfq = self._create_rfq()
        # Create a quotation with total below 50k
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 1,
            'unit_price': 30000,  # Total = 30,000 (below 50k)
        })
        quotation.action_submit()
        quotation.action_select()
        self.assertEqual(rfq.approval_required, 1,
                         'Below 50k should require only 1 approver')

    def test_threshold_above_50k_requires_2_approvers(self):
        """Total above threshold_1 (50k) should require 2 approvers."""
        rfq = self._create_rfq()
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 1,
            'unit_price': 100000,  # Total = 100,000 (above 50k)
        })
        quotation.action_submit()
        quotation.action_select()
        self.assertEqual(rfq.approval_required, 2,
                         'Above 50k should require 2 approvers')

    def test_threshold_above_200k_requires_2_approvers(self):
        """Total above threshold_2 (200k) should still require 2 approvers."""
        rfq = self._create_rfq()
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 1,
            'unit_price': 300000,  # Total = 300,000 (above 200k)
        })
        quotation.action_submit()
        quotation.action_select()
        self.assertEqual(rfq.approval_required, 2,
                         'Above 200k should still require 2 approvers')

    # ------------------------------------------------------------------
    # Approval Initiation Tests
    # ------------------------------------------------------------------

    def test_initiate_approval_without_selected_quotation_raises_error(self):
        """Initiating approval without a selected quotation should fail."""
        rfq = self._create_rfq()
        rfq.state = 'compared'
        with self.assertRaises(UserError):
            rfq.action_initiate_approval()

    def test_initiate_approval_without_managers_raises_error(self):
        """Initiating approval with no managers in group should raise UserError."""
        rfq = self._create_rfq()
        rfq.action_send_to_vendors()
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 1,
            'unit_price': 10000,
        })
        quotation.action_submit()
        quotation.action_select()
        # Remove all users from manager group if any
        if self.manager_group:
            manager_users = self.env['res.users'].search([
                ('groups_id', 'in', self.manager_group.id),
            ])
            manager_users.write({
                'groups_id': [(3, self.manager_group.id)],
            })
        with self.assertRaises(UserError):
            rfq.action_initiate_approval()

    # ------------------------------------------------------------------
    # Full Approval → PO Generation Test
    # ------------------------------------------------------------------

    def test_full_approval_generates_po_in_draft(self):
        """Full approval of an RFQ should auto-generate a PO in 'draft' state."""
        rfq = self._create_rfq()
        rfq.action_send_to_vendors()

        # Create and select quotation
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 5,
            'unit_price': 5000,  # 25,000 total (1 approver needed)
        })
        quotation.action_submit()
        quotation.action_select()

        # Ensure a manager exists
        if self.manager_group:
            self.env.user.write({
                'groups_id': [(4, self.manager_group.id)],
            })

        rfq.action_initiate_approval()
        self.assertEqual(rfq.state, 'pending_approval')

        # Approve
        approval = rfq.approval_ids[0]
        approval.action_approve()

        # Verify PO was created
        self.assertEqual(rfq.state, 'po_created',
                         'RFQ state should be po_created after full approval')
        po = self.env['vendorbridge.purchaseorder'].search([
            ('rfq_id', '=', rfq.id),
        ])
        self.assertTrue(po, 'Purchase Order should be created')
        self.assertEqual(po.state, 'draft',
                         'Auto-generated PO should be in draft state')

    # ------------------------------------------------------------------
    # Cancel and Reset Tests
    # ------------------------------------------------------------------

    def test_cancel_rfq(self):
        """Cancelling an RFQ should set state to 'cancelled'."""
        rfq = self._create_rfq()
        rfq.action_cancel()
        self.assertEqual(rfq.state, 'cancelled')

    def test_reset_to_draft(self):
        """Resetting an RFQ should set state back to 'draft'."""
        rfq = self._create_rfq()
        rfq.action_send_to_vendors()
        rfq.action_reset_draft()
        self.assertEqual(rfq.state, 'draft')

    # ------------------------------------------------------------------
    # Rejection Cascading Test
    # ------------------------------------------------------------------

    def test_rejection_cancels_rfq(self):
        """Rejecting an approval should cancel the RFQ."""
        rfq = self._create_rfq()
        rfq.action_send_to_vendors()

        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Item A',
            'quantity': 5,
            'unit_price': 5000,
        })
        quotation.action_submit()
        quotation.action_select()

        if self.manager_group:
            self.env.user.write({
                'groups_id': [(4, self.manager_group.id)],
            })

        rfq.action_initiate_approval()
        approval = rfq.approval_ids[0]
        approval.remarks = 'Budget not approved'
        approval.action_reject()

        self.assertEqual(rfq.state, 'cancelled',
                         'RFQ should be cancelled when approval is rejected')
        self.assertEqual(approval.state, 'rejected')
