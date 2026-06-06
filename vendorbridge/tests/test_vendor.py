from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestVendor(TransactionCase):
    """Test vendor registration, approval workflow, and GSTIN validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['res.partner']
        cls.category = cls.env['vendorbridge.vendor.category'].create({
            'name': 'Test Category',
            'description': 'Test vendor category',
        })

    def _create_vendor(self, name='Test Vendor', gst_number=False, **kwargs):
        """Helper to create a vendor partner."""
        vals = {
            'name': name,
            'email': f'{name.lower().replace(" ", "_")}@test.com',
            'is_vendor': True,
            'vendor_status': 'draft',
            'vendor_category_id': self.category.id,
        }
        if gst_number:
            vals['gst_number'] = gst_number
        vals.update(kwargs)
        return self.partner_model.create(vals)

    # ------------------------------------------------------------------
    # GSTIN Validation Tests
    # ------------------------------------------------------------------

    def test_valid_gstin_passes(self):
        """Valid GSTIN format should not raise any error."""
        vendor = self._create_vendor(name='Valid GST Vendor', gst_number='27AABCU9603R1ZM')
        self.assertEqual(vendor.gst_number, '27AABCU9603R1ZM')

    def test_valid_gstin_various_state_codes(self):
        """GSTIN with different valid state codes should be accepted."""
        valid_gstins = [
            '07AABCU9603R1ZM',  # Delhi
            '29AABCU9603R1ZM',  # Karnataka
            '33AABCU9603R1ZM',  # Tamil Nadu
        ]
        for i, gstin in enumerate(valid_gstins):
            vendor = self._create_vendor(
                name=f'GST Vendor {i}', gst_number=gstin,
                email=f'gst_vendor_{i}@test.com',
            )
            self.assertEqual(vendor.gst_number, gstin)

    def test_invalid_gstin_too_short(self):
        """GSTIN shorter than 15 characters should be rejected."""
        with self.assertRaises(ValidationError):
            self._create_vendor(name='Short GST', gst_number='27AABCU960')

    def test_invalid_gstin_wrong_format(self):
        """GSTIN with incorrect structure should be rejected."""
        with self.assertRaises(ValidationError):
            self._create_vendor(name='Bad GST', gst_number='XXAABCU9603R1ZM')

    def test_invalid_gstin_missing_z(self):
        """GSTIN without the mandatory Z in position 14 should be rejected."""
        with self.assertRaises(ValidationError):
            self._create_vendor(name='No Z GST', gst_number='27AABCU9603R1AM')

    def test_empty_gstin_allowed(self):
        """Empty/no GSTIN should be allowed (it's optional)."""
        vendor = self._create_vendor(name='No GST Vendor')
        self.assertFalse(vendor.gst_number)

    # ------------------------------------------------------------------
    # Vendor Status Lifecycle Tests
    # ------------------------------------------------------------------

    def test_vendor_default_status_is_draft(self):
        """New vendor should be created in 'draft' status by default."""
        vendor = self._create_vendor(name='Draft Vendor')
        self.assertEqual(vendor.vendor_status, 'draft')

    def test_vendor_approve(self):
        """Approving a vendor should change status to 'approved'."""
        vendor = self._create_vendor(name='Approve Vendor', vendor_status='pending')
        vendor.action_approve_vendor()
        self.assertEqual(vendor.vendor_status, 'approved')

    def test_vendor_reject(self):
        """Rejecting a vendor should change status to 'rejected'."""
        vendor = self._create_vendor(name='Reject Vendor', vendor_status='pending')
        vendor.action_reject_vendor()
        self.assertEqual(vendor.vendor_status, 'rejected')

    def test_vendor_block(self):
        """Blocking a vendor should change status to 'blocked'."""
        vendor = self._create_vendor(name='Block Vendor', vendor_status='approved')
        vendor.action_block_vendor()
        self.assertEqual(vendor.vendor_status, 'blocked')

    # ------------------------------------------------------------------
    # Activity Logging Tests
    # ------------------------------------------------------------------

    def test_vendor_approval_creates_activity_log(self):
        """Approving a vendor should create an activity log entry."""
        vendor = self._create_vendor(name='Log Vendor', vendor_status='pending')
        vendor.action_approve_vendor()
        log = self.env['vendorbridge.activitylog'].search([
            ('model_name', '=', 'res.partner'),
            ('record_id', '=', vendor.id),
            ('action', '=', 'Vendor Approved'),
        ])
        self.assertTrue(log, 'Activity log entry should be created on vendor approval')
        self.assertEqual(log.category, 'vendor')

    # ------------------------------------------------------------------
    # Total Orders Compute Test
    # ------------------------------------------------------------------

    def test_total_orders_defaults_to_zero(self):
        """New vendor should have 0 total orders."""
        vendor = self._create_vendor(name='Zero Orders Vendor')
        vendor._compute_total_orders()
        self.assertEqual(vendor.total_orders, 0)

    def test_non_vendor_total_orders_is_zero(self):
        """Non-vendor partner should always have 0 total orders."""
        partner = self.partner_model.create({
            'name': 'Not A Vendor',
            'is_vendor': False,
        })
        partner._compute_total_orders()
        self.assertEqual(partner.total_orders, 0)
