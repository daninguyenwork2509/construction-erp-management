from odoo import models, fields, api
from odoo.exceptions import UserError


class SaleOrderTemplate(models.Model):
    """Template loader - Tự động load BOQ template dựa vào construction_type"""
    _inherit = 'sale.order'

    def _get_template_by_construction_type(self):
        """
        Load template (boq.category + boq.job) dựa vào construction_type

        Flow:
        - civil_structural → Load CS.PD, CS.XT, CS.LT... (Xây dựng)
        - fitout_renovation → Load FR.TD, FR.OL, FR.SN... (Hoàn thiện)
        - decoration → Load DC.BH, DC.NR, DC.RE... (Trang trí)
        """
        self.ensure_one()

        if not self.construction_type:
            raise UserError("Vui lòng chọn Loại hình thi công trước!")

        # Tìm tất cả boq.category có work_type = construction_type
        categories = self.env['boq.category'].search([
            ('work_type', '=', self.construction_type)
        ], order='sequence')

        if not categories:
            raise UserError(f"Không tìm thấy Hạng mục nào cho loại hình '{self.construction_type}'")

        # Tìm tất cả boq.job liên kết với các category này
        jobs = self.env['boq.job'].search([
            ('category_code', 'in', [cat.code for cat in categories])
        ], order='sequence')

        return {
            'categories': categories,
            'jobs': jobs,
            'construction_type': self.construction_type,
        }

    def action_export_template_excel(self):
        """
        Export Excel template để Thu mua gọi hàng
        - Xuất tất cả job thuộc loại hình thi công
        - Format: Line ID | Category | Job | Product | Qty | UoM | Unit Price (trống)
        """
        self.ensure_one()

        if self.state != 'sale':
            raise UserError("Chỉ có thể export khi Báo giá ở trạng thái 'sale' (Đã chốt)")

        try:
            import io
            import xlsxwriter
        except ImportError:
            raise UserError("Thư viện xlsxwriter chưa được cài đặt. Vui lòng liên hệ IT!")

        template = self._get_template_by_construction_type()

        # Tạo file Excel in-memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Template')

        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1F4E78',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
        })

        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'num_format': '#,##0',
        })

        # Header
        headers = ['Line ID', 'Hạng mục (L1)', 'Công tác (L2)', 'Tên Vật tư', 'ĐVT', 'Số lượng', 'Đơn giá thầu phụ', 'Thành tiền']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Dữ liệu
        row = 1
        line_id = 1
        for job in template['jobs']:
            category = job.category_id
            worksheet.write(row, 0, line_id, data_format)
            worksheet.write(row, 1, category.name, data_format)
            worksheet.write(row, 2, job.name, data_format)
            worksheet.write(row, 3, '', data_format)  # Trống cho sản phẩm
            worksheet.write(row, 4, job.default_uom, data_format)
            worksheet.write(row, 5, '', data_format)  # Số lượng - để trống
            worksheet.write(row, 6, '', data_format)  # Đơn giá - để trống
            worksheet.write(row, 7, '', data_format)  # Thành tiền - để trống

            row += 1
            line_id += 1

        # Điều chỉnh độ rộng cột
        worksheet.set_column('A:A', 10)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 25)
        worksheet.set_column('D:D', 25)
        worksheet.set_column('E:E', 12)
        worksheet.set_column('F:H', 15)

        workbook.close()
        output.seek(0)

        # Lưu attachment
        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name}_BOQ_Template.xlsx",
            'type': 'binary',
            'datas': output.getvalue().hex(),
            'res_model': 'sale.order',
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_import_template_excel(self):
        """
        Import Excel - Thu mua điền giá → Cập nhật purchase_price
        - Validate: Không được lỗ (purchase_price > price_unit)
        - Auto-create Purchase Order
        """
        self.ensure_one()

        if self.state != 'sale':
            raise UserError("Chỉ có thể import khi Báo giá ở trạng thái 'sale'")

        # Placeholder - Sẽ implement chi tiết khi có file upload
        raise UserError("Chức năng Import sẽ được implement ở bước tiếp theo")

    def get_template_info(self):
        """Trả về thông tin template dưới dạng JSON"""
        self.ensure_one()

        template = self._get_template_by_construction_type()

        return {
            'construction_type': template['construction_type'],
            'categories_count': len(template['categories']),
            'jobs_count': len(template['jobs']),
            'categories': [
                {'code': cat.code, 'name': cat.name}
                for cat in template['categories']
            ],
            'jobs': [
                {
                    'code': job.code,
                    'name': job.name,
                    'category': job.category_id.name,
                    'uom': job.default_uom,
                }
                for job in template['jobs']
            ],
        }
