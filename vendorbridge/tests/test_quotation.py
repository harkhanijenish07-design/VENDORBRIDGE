from odoo.tests.common import TransactionCase


class TestQuotation(TransactionCase):
    """Test quotation submission, selection, rejection, and lowest-price computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['vendorbridge.vendor.category'].create({
            'name': 'Furniture',
        })
        cls.vendor_1 = cls.env['res.partner'].create({
            'name': 'Vendor One',
            'email': 'v1@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
        })
        cls.vendor_2 = cls.env['res.partner'].create({
            'name': 'Vendor Two',
            'email': 'v2@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
        })
        cls.vendor_3 = cls.env['res.partner'].create({
            'name': 'Vendor Three',
            'email': 'v3@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
        })
        # Create RFQ with line items
        cls.rfq = cls.env['vendorbridge.rfq'].create({
            'title': 'Office Furniture Q2',
            'category_id': cls.category.id,
            'deadline': '2026-12-31',
            'vendor_ids': [(6, 0, [cls.vendor_1.id, cls.vendor_2.id, cls.vendor_3.id])],
        })
        cls.rfq_line = cls.env['vendorbridge.rfq.line'].create({
            'rfq_id': cls.rfq.id,
            'description': 'Ergonomic Chair',
            'quantity': 20,
        })
        cls.rfq.action_send_to_vendors()

    def _create_quotation(self, vendor, unit_price, discount_percent=0, delivery_days=7):
        """Helper to create a submitted quotation."""
        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': self.rfq.id,
            'vendor_id': vendor.id,
            'discount_percent': discount_percent,
            'delivery_days': delivery_days,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'rfq_line_id': self.rfq_line.id,
            'description': 'Ergonomic Chair',
            'quantity': 20,
            'unit_price': unit_price,
            'gst_rate': '18',
        })
        return quotation

    # ------------------------------------------------------------------
    # Quotation Creation & Sequence Tests
    # ------------------------------------------------------------------

    def test_quotation_auto_sequence(self):
        """Quotation should get an auto-generated sequence number."""
        q = self._create_quotation(self.vendor_1, 5000)
        self.assertNotEqual(q.name, 'New')

    def test_quotation_initial_state_is_draft(self):
        """Newly created quotation should be in 'draft' state."""
        q = self._create_quotation(self.vendor_1, 5000)
        self.assertEqual(q.state, 'draft')

    # ------------------------------------------------------------------
    # Amount Computation Tests
    # ------------------------------------------------------------------

    def test_subtotal_calculation(self):
        """Subtotal should equal sum of line subtotals (qty * price)."""
        q = self._create_quotation(self.vendor_1, 5000)  # 20 * 5000 = 100,000
        self.assertAlmostEqual(q.subtotal, 100000.0, places=2)

    def test_discount_calculation(self):
        """Discount should be correctly computed from discount_percent."""
        q = self._create_quotation(self.vendor_1, 5000, discount_percent=10)
        # Subtotal = 100,000; Discount 10% = 10,000
        self.assertAlmostEqual(q.discount_amount, 10000.0, places=2)
        self.assertAlmostEqual(q.total, 90000.0, places=2)

    def test_zero_discount(self):
        """Zero discount should leave total equal to subtotal."""
        q = self._create_quotation(self.vendor_1, 5000, discount_percent=0)
        self.assertAlmostEqual(q.total, q.subtotal, places=2)

    # ------------------------------------------------------------------
    # Delivery Date Computation Tests
    # ------------------------------------------------------------------

    def test_delivery_date_computed(self):
        """Delivery date should be RFQ deadline + delivery_days."""
        from datetime import date, timedelta
        q = self._create_quotation(self.vendor_1, 5000, delivery_days=15)
        expected = date(2026, 12, 31) + timedelta(days=15)
        self.assertEqual(q.delivery_date, expected)

    def test_delivery_date_no_days(self):
        """Delivery date should be False when delivery_days is 0."""
        q = self._create_quotation(self.vendor_1, 5000, delivery_days=0)
        self.assertFalse(q.delivery_date)

    # ------------------------------------------------------------------
    # Submission Tests
    # ------------------------------------------------------------------

    def test_submit_changes_state(self):
        """Submitting a quotation should change state to 'submitted'."""
        q = self._create_quotation(self.vendor_1, 5000)
        q.action_submit()
        self.assertEqual(q.state, 'submitted')

    def test_submit_updates_rfq_to_quoted(self):
        """First quotation submission should move RFQ to 'quoted' state."""
        # Reset RFQ state for this test
        rfq = self.env['vendorbridge.rfq'].create({
            'title': 'Submit Test RFQ',
            'category_id': self.category.id,
            'deadline': '2026-12-31',
            'vendor_ids': [(6, 0, [self.vendor_1.id])],
        })
        self.env['vendorbridge.rfq.line'].create({
            'rfq_id': rfq.id,
            'description': 'Test Item',
            'quantity': 1,
        })
        rfq.action_send_to_vendors()
        self.assertEqual(rfq.state, 'sent')

        q = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': self.vendor_1.id,
            'delivery_days': 7,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': q.id,
            'description': 'Test Item',
            'quantity': 1,
            'unit_price': 1000,
        })
        q.action_submit()
        self.assertEqual(rfq.state, 'quoted')

    def test_submit_creates_activity_log(self):
        """Submitting a quotation should create an activity log."""
        q = self._create_quotation(self.vendor_1, 5000)
        q.action_submit()
        log = self.env['vendorbridge.activitylog'].search([
            ('model_name', '=', 'vendorbridge.quotation'),
            ('record_id', '=', q.id),
            ('action', '=', 'Quotation Submitted'),
        ])
        self.assertTrue(log, 'Activity log should exist for submitted quotation')

    # ------------------------------------------------------------------
    # Selection & Rejection Tests
    # ------------------------------------------------------------------

    def test_select_winner(self):
        """Selecting a quotation should mark it as selected."""
        q1 = self._create_quotation(self.vendor_1, 5000)
        q2 = self._create_quotation(self.vendor_2, 6000)
        q1.action_submit()
        q2.action_submit()
        q1.action_select()

        self.assertTrue(q1.is_selected)
        self.assertEqual(q1.state, 'selected')

    def test_select_winner_rejects_siblings(self):
        """Selecting one quotation should reject all other sibling quotations."""
        q1 = self._create_quotation(self.vendor_1, 5000)
        q2 = self._create_quotation(self.vendor_2, 6000)
        q3 = self._create_quotation(self.vendor_3, 7000)
        q1.action_submit()
        q2.action_submit()
        q3.action_submit()
        q1.action_select()

        self.assertEqual(q2.state, 'rejected')
        self.assertEqual(q3.state, 'rejected')
        self.assertFalse(q2.is_selected)
        self.assertFalse(q3.is_selected)

    def test_select_winner_updates_rfq_state(self):
        """Selecting a winner should move RFQ to 'compared' state."""
        q1 = self._create_quotation(self.vendor_1, 5000)
        q1.action_submit()
        q1.action_select()
        self.assertEqual(self.rfq.state, 'compared')

    def test_reject_quotation(self):
        """Explicitly rejecting a quotation should mark it rejected."""
        q = self._create_quotation(self.vendor_1, 5000)
        q.action_submit()
        q.action_reject()
        self.assertEqual(q.state, 'rejected')
        self.assertFalse(q.is_selected)

    # ------------------------------------------------------------------
    # Lowest Price Compute Tests
    # ------------------------------------------------------------------

    def test_is_lowest_flag(self):
        """is_lowest should be True for the cheapest submitted quotation."""
        q1 = self._create_quotation(self.vendor_1, 5000)   # 100,000
        q2 = self._create_quotation(self.vendor_2, 6000)   # 120,000
        q3 = self._create_quotation(self.vendor_3, 4000)   # 80,000
        q1.action_submit()
        q2.action_submit()
        q3.action_submit()

        self.assertTrue(q3.is_lowest, 'Cheapest quotation should be flagged is_lowest')
        self.assertFalse(q1.is_lowest)
        self.assertFalse(q2.is_lowest)
