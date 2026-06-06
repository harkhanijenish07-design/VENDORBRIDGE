from odoo.tests.common import TransactionCase


class TestGSTCalculations(TransactionCase):
    """Test GST split calculations: CGST+SGST for intra-state, IGST for inter-state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get Indian states for GST testing
        cls.state_maharashtra = cls.env.ref('base.state_in_mh', raise_if_not_found=False)
        cls.state_karnataka = cls.env.ref('base.state_in_ka', raise_if_not_found=False)

        # If Indian states aren't available, create mock states
        if not cls.state_maharashtra:
            country_in = cls.env['res.country'].search([('code', '=', 'IN')], limit=1)
            if not country_in:
                country_in = cls.env['res.country'].create({
                    'name': 'India', 'code': 'IN',
                })
            cls.state_maharashtra = cls.env['res.country.state'].create({
                'name': 'Maharashtra', 'code': 'MH',
                'country_id': country_in.id,
            })
            cls.state_karnataka = cls.env['res.country.state'].create({
                'name': 'Karnataka', 'code': 'KA',
                'country_id': country_in.id,
            })

        # Set company state to Maharashtra
        cls.env.company.state_id = cls.state_maharashtra

        cls.category = cls.env['vendorbridge.vendor.category'].create({
            'name': 'GST Test Category',
        })

        # Intra-state vendor (same state as company → CGST+SGST)
        cls.vendor_same_state = cls.env['res.partner'].create({
            'name': 'Intra-State Vendor',
            'email': 'intra@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
            'state_id': cls.state_maharashtra.id,
        })

        # Inter-state vendor (different state → IGST)
        cls.vendor_diff_state = cls.env['res.partner'].create({
            'name': 'Inter-State Vendor',
            'email': 'inter@test.com',
            'is_vendor': True,
            'vendor_status': 'approved',
            'state_id': cls.state_karnataka.id,
        })

    def _create_full_chain(self, vendor, line_price=10000, line_qty=10, gst_rate='18'):
        """Helper to create RFQ → Quotation → PO → Invoice chain for a given vendor."""
        rfq = self.env['vendorbridge.rfq'].create({
            'title': f'GST Test RFQ for {vendor.name}',
            'category_id': self.category.id,
            'deadline': '2026-12-31',
            'vendor_ids': [(6, 0, [vendor.id])],
        })
        self.env['vendorbridge.rfq.line'].create({
            'rfq_id': rfq.id,
            'description': 'Test Product',
            'quantity': line_qty,
        })
        rfq.action_send_to_vendors()

        quotation = self.env['vendorbridge.quotation'].create({
            'rfq_id': rfq.id,
            'vendor_id': vendor.id,
            'delivery_days': 7,
        })
        self.env['vendorbridge.quotation.line'].create({
            'quotation_id': quotation.id,
            'description': 'Test Product',
            'quantity': line_qty,
            'unit_price': line_price,
            'gst_rate': gst_rate,
        })
        quotation.action_submit()
        quotation.action_select()

        # Create PO directly (skipping approval for GST-focused tests)
        po = self.env['vendorbridge.purchaseorder'].create({
            'quotation_id': quotation.id,
            'company_id': self.env.company.id,
        })
        self.env['vendorbridge.purchase.order.line'].create({
            'order_id': po.id,
            'description': 'Test Product',
            'quantity': line_qty,
            'price_unit': line_price,
        })

        # Create Invoice
        invoice = self.env['vendorbridge.invoice'].create({
            'purchase_order_id': po.id,
            'company_id': self.env.company.id,
            'gst_rate': gst_rate,
        })
        self.env['vendorbridge.invoice.line'].create({
            'invoice_id': invoice.id,
            'description': 'Test Product',
            'quantity': line_qty,
            'price_unit': line_price,
        })
        return invoice

    # ------------------------------------------------------------------
    # GST Type Detection Tests
    # ------------------------------------------------------------------

    def test_intra_state_gst_type(self):
        """Same-state vendor+company should get CGST+SGST type."""
        invoice = self._create_full_chain(self.vendor_same_state)
        self.assertEqual(invoice.gst_type, 'cgst_sgst',
                         'Intra-state should yield CGST+SGST')

    def test_inter_state_gst_type(self):
        """Different-state vendor+company should get IGST type."""
        invoice = self._create_full_chain(self.vendor_diff_state)
        self.assertEqual(invoice.gst_type, 'igst',
                         'Inter-state should yield IGST')

    # ------------------------------------------------------------------
    # CGST + SGST Calculation Tests
    # ------------------------------------------------------------------

    def test_cgst_sgst_at_18_percent(self):
        """CGST and SGST should each be 9% of taxable amount at 18% GST."""
        invoice = self._create_full_chain(
            self.vendor_same_state, line_price=10000, line_qty=10, gst_rate='18'
        )
        # Taxable = 10,000 * 10 = 100,000
        # CGST = SGST = 100,000 * 0.18 / 2 = 9,000
        self.assertAlmostEqual(invoice.amount_untaxed, 100000.0, places=2)
        self.assertAlmostEqual(invoice.cgst_amount, 9000.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 9000.0, places=2)
        self.assertAlmostEqual(invoice.igst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 18000.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 118000.0, places=2)

    def test_cgst_sgst_at_5_percent(self):
        """CGST+SGST at 5% GST: each should be 2.5% of taxable."""
        invoice = self._create_full_chain(
            self.vendor_same_state, line_price=20000, line_qty=5, gst_rate='5'
        )
        # Taxable = 100,000; CGST = SGST = 2,500
        self.assertAlmostEqual(invoice.cgst_amount, 2500.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 2500.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 5000.0, places=2)

    def test_cgst_sgst_at_12_percent(self):
        """CGST+SGST at 12% GST: each should be 6% of taxable."""
        invoice = self._create_full_chain(
            self.vendor_same_state, line_price=10000, line_qty=10, gst_rate='12'
        )
        # Taxable = 100,000; CGST = SGST = 6,000
        self.assertAlmostEqual(invoice.cgst_amount, 6000.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 6000.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 12000.0, places=2)

    def test_cgst_sgst_at_28_percent(self):
        """CGST+SGST at 28% GST: each should be 14% of taxable."""
        invoice = self._create_full_chain(
            self.vendor_same_state, line_price=10000, line_qty=10, gst_rate='28'
        )
        # Taxable = 100,000; CGST = SGST = 14,000
        self.assertAlmostEqual(invoice.cgst_amount, 14000.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 14000.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 28000.0, places=2)

    # ------------------------------------------------------------------
    # IGST Calculation Tests
    # ------------------------------------------------------------------

    def test_igst_at_18_percent(self):
        """IGST should be full 18% of taxable amount for inter-state."""
        invoice = self._create_full_chain(
            self.vendor_diff_state, line_price=10000, line_qty=10, gst_rate='18'
        )
        # Taxable = 100,000; IGST = 18,000
        self.assertAlmostEqual(invoice.amount_untaxed, 100000.0, places=2)
        self.assertAlmostEqual(invoice.cgst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.igst_amount, 18000.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 18000.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 118000.0, places=2)

    def test_igst_at_5_percent(self):
        """IGST at 5% for inter-state vendor."""
        invoice = self._create_full_chain(
            self.vendor_diff_state, line_price=20000, line_qty=5, gst_rate='5'
        )
        # Taxable = 100,000; IGST = 5,000
        self.assertAlmostEqual(invoice.igst_amount, 5000.0, places=2)
        self.assertAlmostEqual(invoice.cgst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 0.0, places=2)

    def test_igst_at_28_percent(self):
        """IGST at 28% for inter-state vendor."""
        invoice = self._create_full_chain(
            self.vendor_diff_state, line_price=10000, line_qty=10, gst_rate='28'
        )
        # Taxable = 100,000; IGST = 28,000
        self.assertAlmostEqual(invoice.igst_amount, 28000.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 28000.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 128000.0, places=2)

    # ------------------------------------------------------------------
    # Zero GST Rate Test
    # ------------------------------------------------------------------

    def test_zero_gst_rate(self):
        """0% GST should result in zero tax amounts for both types."""
        invoice = self._create_full_chain(
            self.vendor_same_state, line_price=10000, line_qty=10, gst_rate='0'
        )
        self.assertAlmostEqual(invoice.cgst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.sgst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.igst_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.tax_amount, 0.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 100000.0, places=2)

    # ------------------------------------------------------------------
    # Grand Total Integrity Test
    # ------------------------------------------------------------------

    def test_grand_total_equals_untaxed_plus_tax(self):
        """amount_total should always equal amount_untaxed + tax_amount."""
        for vendor in [self.vendor_same_state, self.vendor_diff_state]:
            for rate in ['0', '5', '12', '18', '28']:
                invoice = self._create_full_chain(
                    vendor, line_price=7500, line_qty=8, gst_rate=rate
                )
                self.assertAlmostEqual(
                    invoice.amount_total,
                    invoice.amount_untaxed + invoice.tax_amount,
                    places=2,
                    msg=f'Total mismatch for {vendor.name} at {rate}% GST',
                )

    # ------------------------------------------------------------------
    # Due Date Computation Test
    # ------------------------------------------------------------------

    def test_due_date_30_days_from_invoice_date(self):
        """Due date should be 30 days after invoice date."""
        from datetime import timedelta
        invoice = self._create_full_chain(self.vendor_same_state)
        if invoice.invoice_date:
            expected = invoice.invoice_date + timedelta(days=30)
            self.assertEqual(invoice.due_date, expected)
