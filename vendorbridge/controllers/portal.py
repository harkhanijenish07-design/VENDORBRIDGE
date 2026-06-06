import base64
import logging
import re
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Indian GSTIN format: 2-digit state code + 10-char PAN + entity number + Z + check digit
GSTIN_REGEX = re.compile(
    r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
)

# Maximum file upload size: 10 MB
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


class VendorBridgePortal(http.Controller):

    @http.route('/vendor', type='http', auth='public', website=True)
    def vendor_home(self, **kwargs):
        """Vendor portal home - redirect to dashboard or login."""
        if request.env.user._is_public():
            return request.redirect('/web/login?redirect=/vendor/dashboard')
        return request.redirect('/vendor/dashboard')

    @http.route('/vendor/signup', type='http', auth='public', website=True,
                methods=['GET', 'POST'])
    def vendor_signup(self, **post):
        """Vendor self-registration page."""
        if request.httprequest.method == 'POST':
            return self._process_signup(post)
        return request.render('vendorbridge.vendor_signup_page', {
            'error': None,
            'success': False,
        })

    def _process_signup(self, post):
        """Process vendor registration form submission."""
        name = post.get('name', '').strip()
        email = post.get('email', '').strip()
        phone = post.get('phone', '').strip()
        gst_number = post.get('gst_number', '').strip().upper()
        password = post.get('password', '')
        confirm_password = post.get('confirm_password', '')

        # Validation
        if not all([name, email, phone, password]):
            return request.render('vendorbridge.vendor_signup_page', {
                'error': 'Please fill in all required fields.',
                'success': False,
            })

        if password != confirm_password:
            return request.render('vendorbridge.vendor_signup_page', {
                'error': 'Passwords do not match.',
                'success': False,
            })

        if len(password) < 8:
            return request.render('vendorbridge.vendor_signup_page', {
                'error': 'Password must be at least 8 characters.',
                'success': False,
            })

        # GSTIN structural validation
        if gst_number:
            if len(gst_number) != 15:
                return request.render('vendorbridge.vendor_signup_page', {
                    'error': f'GSTIN must be exactly 15 characters. Got {len(gst_number)}.',
                    'success': False,
                })
            if not GSTIN_REGEX.match(gst_number):
                return request.render('vendorbridge.vendor_signup_page', {
                    'error': (
                        f'Invalid GSTIN format: "{gst_number}". '
                        'Expected: 2-digit state code + PAN + entity number + Z + check digit. '
                        'Example: 27AABCU9603R1ZM'
                    ),
                    'success': False,
                })

        # Check if email already exists
        existing = request.env['res.partner'].sudo().search([
            ('email', '=', email)
        ], limit=1)
        if existing:
            return request.render('vendorbridge.vendor_signup_page', {
                'error': 'An account with this email already exists.',
                'success': False,
            })

        try:
            # Create partner
            partner = request.env['res.partner'].sudo().create({
                'name': name,
                'email': email,
                'phone': phone,
                'gst_number': gst_number or False,
                'is_vendor': True,
                'vendor_status': 'pending',
                'supplier_rank': 1,
            })

            # Create portal user
            user = request.env['res.users'].sudo().create({
                'login': email,
                'password': password,
                'partner_id': partner.id,
                'groups_id': [(6, 0, [
                    request.env.ref('base.group_portal').id,
                ])],
            })

            # Send notification to admin
            template = request.env.ref(
                'vendorbridge.mail_template_vendor_signup_pending',
                raise_if_not_found=False,
            )
            if template:
                admin_users = request.env['res.users'].sudo().search([
                    ('groups_id', 'in', request.env.ref(
                        'vendorbridge.group_admin'
                    ).id)
                ])
                for admin in admin_users:
                    template.sudo().send_mail(
                        partner.id, force_send=False,
                        email_values={'email_to': admin.email},
                    )

            # Log activity
            request.env['vendorbridge.activitylog'].sudo().create({
                'model_name': 'res.partner',
                'record_id': partner.id,
                'record_name': partner.name,
                'action': 'Vendor Registered',
                'category': 'vendor',
                'user_id': user.id,
                'details': f'New vendor registered: {name} ({email})',
            })

            return request.render('vendorbridge.vendor_signup_page', {
                'error': None,
                'success': True,
            })

        except Exception as e:
            _logger.exception('Vendor signup error')
            return request.render('vendorbridge.vendor_signup_page', {
                'error': f'Registration failed: {str(e)}',
                'success': False,
            })

    @http.route('/vendor/dashboard', type='http', auth='user', website=True)
    def vendor_dashboard(self, **kwargs):
        """Vendor portal dashboard with stat cards."""
        partner = request.env.user.partner_id
        rfq_count = request.env['vendorbridge.rfq'].sudo().search_count([
            ('vendor_ids', 'in', partner.id),
            ('state', 'in', ['sent', 'quoted', 'compared']),
        ])
        po_count = request.env['vendorbridge.purchaseorder'].sudo().search_count([
            ('vendor_id', '=', partner.id),
        ])
        quotation_count = request.env['vendorbridge.quotation'].sudo().search_count([
            ('vendor_id', '=', partner.id),
        ])
        return request.render('vendorbridge.vendor_portal_dashboard', {
            'rfq_count': rfq_count,
            'po_count': po_count,
            'quotation_count': quotation_count,
        })

    @http.route('/vendor/rfq', type='http', auth='user', website=True)
    def vendor_rfq_list(self, **kwargs):
        """List RFQs assigned to the current vendor."""
        partner = request.env.user.partner_id
        rfqs = request.env['vendorbridge.rfq'].sudo().search([
            ('vendor_ids', 'in', partner.id),
            ('state', '!=', 'draft'),
        ])
        return request.render('vendorbridge.vendor_portal_rfq_list', {
            'rfqs': rfqs,
        })

    @http.route('/vendor/rfq/<int:rfq_id>', type='http', auth='user', website=True)
    def vendor_rfq_detail(self, rfq_id, **kwargs):
        """View specific RFQ details."""
        partner = request.env.user.partner_id
        rfq = request.env['vendorbridge.rfq'].sudo().browse(rfq_id)
        if not rfq.exists() or partner not in rfq.vendor_ids:
            return request.redirect('/vendor/rfq')
        return request.render('vendorbridge.vendor_portal_rfq_detail', {
            'rfq': rfq,
        })

    @http.route('/vendor/quotation/<int:rfq_id>/submit', type='http',
                auth='user', website=True, methods=['GET', 'POST'])
    def vendor_quotation_submit(self, rfq_id, **post):
        """Submit or view quotation form for an RFQ."""
        partner = request.env.user.partner_id
        rfq = request.env['vendorbridge.rfq'].sudo().browse(rfq_id)

        if not rfq.exists() or partner not in rfq.vendor_ids:
            return request.redirect('/vendor/rfq')

        if request.httprequest.method == 'POST':
            return self._process_quotation_submission(rfq, partner, post)

        return request.render('vendorbridge.vendor_portal_quotation_submit', {
            'rfq': rfq,
            'error': None,
            'success': False,
        })

    def _process_quotation_submission(self, rfq, partner, post):
        """Process quotation form submission with file attachment handling."""
        try:
            # Create quotation
            quotation = request.env['vendorbridge.quotation'].sudo().create({
                'rfq_id': rfq.id,
                'vendor_id': partner.id,
                'discount_percent': float(post.get('discount_percent', 0)),
                'delivery_days': int(post.get('delivery_days', 0)),
                'notes': post.get('notes', ''),
            })

            # Create quotation lines
            for line in rfq.line_ids:
                price_key = f'price_{line.id}'
                gst_key = f'gst_{line.id}'
                unit_price = float(post.get(price_key, 0))
                gst_rate = post.get(gst_key, '18')

                request.env['vendorbridge.quotation.line'].sudo().create({
                    'quotation_id': quotation.id,
                    'rfq_line_id': line.id,
                    'description': line.description,
                    'quantity': line.quantity,
                    'unit_price': unit_price,
                    'gst_rate': gst_rate,
                })

            # Process file attachments from the upload field
            uploaded_files = request.httprequest.files.getlist('attachments')
            attachment_ids = []
            for uploaded_file in uploaded_files:
                if uploaded_file and uploaded_file.filename:
                    # Read file content with size guard to prevent memory timeouts
                    file_content = uploaded_file.read()
                    if len(file_content) > MAX_UPLOAD_SIZE:
                        return request.render(
                            'vendorbridge.vendor_portal_quotation_submit', {
                                'rfq': rfq,
                                'error': (
                                    f'File "{uploaded_file.filename}" exceeds the '
                                    f'maximum upload size of '
                                    f'{MAX_UPLOAD_SIZE // (1024 * 1024)} MB. '
                                    f'Please upload a smaller file.'
                                ),
                                'success': False,
                            })
                    # Create ir.attachment record
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': uploaded_file.filename,
                        'type': 'binary',
                        'datas': base64.b64encode(file_content),
                        'res_model': 'vendorbridge.quotation',
                        'res_id': quotation.id,
                        'mimetype': (
                            uploaded_file.content_type
                            or 'application/octet-stream'
                        ),
                    })
                    attachment_ids.append(attachment.id)

            # Link attachments to quotation via many2many field
            if attachment_ids:
                quotation.sudo().write({
                    'attachment_ids': [(6, 0, attachment_ids)],
                })

            # Submit the quotation
            quotation.sudo().action_submit()

            return request.render('vendorbridge.vendor_portal_quotation_submit', {
                'rfq': rfq,
                'error': None,
                'success': True,
            })

        except Exception as e:
            _logger.exception('Quotation submission error')
            return request.render('vendorbridge.vendor_portal_quotation_submit', {
                'rfq': rfq,
                'error': f'Submission failed: {str(e)}',
                'success': False,
            })

    @http.route('/vendor/purchaseorder', type='http', auth='user', website=True)
    def vendor_po_list(self, **kwargs):
        """List purchase orders for the current vendor."""
        partner = request.env.user.partner_id
        purchase_orders = request.env['vendorbridge.purchaseorder'].sudo().search([
            ('vendor_id', '=', partner.id),
        ])
        return request.render('vendorbridge.vendor_portal_po_list', {
            'purchase_orders': purchase_orders,
        })

