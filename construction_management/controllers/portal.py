from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, AccessDenied
import logging

_logger = logging.getLogger(__name__)


class ConstructionPortal(http.Controller):
    """
    Portal Controller - Duyệt VO & Ký điện tử
    Routes: /my/sale-order/<id>?access_token=...
    """

    def _get_sale_order(self, order_id, access_token=None):
        """
        Lấy Sale Order + kiểm tra access_token.
        Nếu token không khớp → AccessDenied
        """
        try:
            order_id = int(order_id)
        except (ValueError, TypeError):
            raise AccessDenied()

        order = request.env['sale.order'].sudo().browse(order_id)

        if not order.exists():
            raise AccessDenied()

        # Kiểm tra access_token (bắt buộc nếu user không logged in)
        if not request.env.user._is_admin():
            if not access_token or access_token != order.access_token:
                _logger.warning(
                    f"Portal access denied: Invalid token for SO {order_id}"
                )
                raise AccessDenied()

        return order

    # ==================== MAIN PORTAL VIEW ====================
    @http.route(
        '/my/sale-order/<int:order_id>',
        type='http',
        auth='public',
        website=True,
        csrf=False
    )
    def portal_sale_order_view(self, order_id, access_token=None, **kw):
        """
        Trang chính: Duyệt VO (quotation/sales order).

        Flow:
        1. Kiểm tra token → AccessDenied nếu sai
        2. Nếu chưa verify SĐT → Redirect tới verification page
        3. Nếu đã verify + chưa ký → Hiển thị form ký
        4. Nếu đã ký → Hiển thị confirmation
        """
        try:
            order = self._get_sale_order(order_id, access_token)
        except AccessDenied:
            return request.render('website.403')

        # Step 1: Kiểm tra xác thực SĐT
        if not order.is_portal_verified:
            # Chuyển hướng tới trang verification
            return request.redirect(
                f'/my/sale-order-verify/{order_id}?access_token={access_token or ""}'
            )

        # Step 2: Hiển thị form ký (nếu chưa ký)
        # Tạo context để truyền cho template
        values = {
            'order': order,
            'access_token': access_token,
        }

        return request.render(
            'construction_management.portal_sale_order_view',
            values
        )

    # ==================== PHONE VERIFICATION PAGE ====================
    @http.route(
        '/my/sale-order-verify/<int:order_id>',
        type='http',
        auth='public',
        website=True,
        csrf=False
    )
    def portal_sale_order_verify(self, order_id, access_token=None, **kw):
        """
        Trang xác thực SĐT (Mini-OTP).

        POST params:
        - phone: SĐT nhập vào
        - verify_action: 'verify' | 'skip'

        Logic:
        - Display form: "Nhập SĐT của bạn"
        - User submit → Kiểm tra _normalize_phone()
        - Nếu khớp với partner.phone/mobile → Verify success
        - Nếu không → Error message + form lại
        """
        try:
            order = self._get_sale_order(order_id, access_token)
        except AccessDenied:
            return request.render('website.403')

        # Handle POST: Verify phone
        if request.httprequest.method == 'POST':
            phone_input = kw.get('phone', '').strip()
            verify_action = kw.get('verify_action', 'verify')

            if verify_action == 'verify' and phone_input:
                # Xác thực SĐT
                is_valid = order.verify_portal_access(phone_input)

                if is_valid:
                    # Log IP address
                    client_ip = request.httprequest.remote_addr
                    order._log_portal_access(
                        action='PORTAL_ACCESSED',
                        phone=phone_input,
                        ip=client_ip
                    )

                    # Chuyển hướng tới trang ký
                    return request.redirect(
                        f'/my/sale-order/{order_id}?access_token={access_token or ""}'
                    )
                else:
                    # Xác thực thất bại
                    error_msg = "❌ Số điện thoại xác thực không chính xác!"
            else:
                error_msg = None

        # Hiển thị form verification
        values = {
            'order': order,
            'access_token': access_token,
            'error_msg': kw.get('error_msg', ''),
            'partner_name': order.partner_id.name,
        }

        return request.render(
            'construction_management.portal_sale_order_verify',
            values
        )

    # ==================== SIGN ENDPOINT ====================
    @http.route(
        '/my/sale-order-sign/<int:order_id>',
        type='json',
        auth='public',
        website=True,
        csrf=False
    )
    def portal_sale_order_sign(self, order_id, access_token=None, **kw):
        """
        AJAX Endpoint: Ký điện tử.

        POST JSON:
        {
            "access_token": "...",
            "phone": "0912345678"
        }

        Response:
        {
            "success": true/false,
            "message": "...",
            "redirect_url": "/my/sale-order/..."
        }
        """
        try:
            order = self._get_sale_order(order_id, access_token)
        except AccessDenied:
            return {
                'success': False,
                'message': '❌ Access denied'
            }

        # Kiểm tra đã verify chưa
        if not order.is_portal_verified:
            return {
                'success': False,
                'message': '❌ Chưa xác thực SĐT'
            }

        try:
            # Lấy IP address
            client_ip = request.httprequest.remote_addr

            # Ký
            phone_verified = order.verification_phone
            order.sign_electronically(phone_verified, ip_address=client_ip)

            return {
                'success': True,
                'message': '✅ Ký điện tử thành công!',
                'redirect_url': f'/my/sale-order/{order_id}?access_token={access_token}'
            }

        except Exception as e:
            _logger.error(f"Error signing order {order_id}: {str(e)}")
            return {
                'success': False,
                'message': f'❌ Lỗi: {str(e)}'
            }

    # ==================== DOWNLOAD PDF ====================
    @http.route(
        '/my/sale-order-pdf/<int:order_id>',
        type='http',
        auth='public',
        website=True,
        csrf=False
    )
    def portal_sale_order_pdf(self, order_id, access_token=None, **kw):
        """
        Download PDF của Sale Order (Quotation/Invoice).
        - Chỉ cho phép download nếu access_token đúng
        - Thêm watermark "ĐÃ KÝ" nếu is_signed_electronically = True
        """
        try:
            order = self._get_sale_order(order_id, access_token)
        except AccessDenied:
            return request.render('website.403')

        # Kiểm tra: Chỉ download nếu đã verify hoặc là admin
        if not request.env.user._is_admin() and not order.is_portal_verified:
            return request.render('website.403')

        try:
            # Tạo PDF (sử dụng report_sale_order)
            report = request.env['ir.actions.report'].sudo().search(
                [('report_name', '=', 'sale.report_saleorder')]
            )

            if not report:
                return request.not_found()

            pdf_content = report._render_qweb_pdf(order.ids)[0]

            # Response
            response = request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="SO_{order.name}.pdf"')
                ]
            )

            return response

        except Exception as e:
            _logger.error(f"Error generating PDF for SO {order_id}: {str(e)}")
            return request.render('website.500')
