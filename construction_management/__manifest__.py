{
    'name': 'Construction Management',
    'version': '1.0.0',
    'category': 'Sales/Project',
    'author': 'BlueBolt Software',
    'summary': 'Module quản lý xây dựng nhà thầu - Báo giá 3 Level BOQ, Khảo sát, Thiết kế',
    'description': '''
        Module tùy biến Odoo cho công ty quản lý xây dựng nhà thầu:
        - Mở rộng Sale Order với construction_type, project_address, estimated_budget, pm_id
        - Mở rộng Project Task với task_stage_type, is_survey_data_locked, design_file_type
        - Tạo mới BOQ Category (Level 1) và BOQ Job (Level 2)
        - Mở rộng Sale Order Line với job_id, is_subcontracted
        - Luồng state machine: lead -> surveying -> waiting_pm -> draft/sent -> sale -> done
        - Ràng buộc: Bắt buộc upload file khảo sát, Kiểm tra thanh toán 50% & 100%
    ''',
    'depends': [
        'base',
        'crm',
        'sale',
        'sale_management',
        'project',
        'purchase',
        'stock',
        'account',
        'web',
    ],
    'data': [
        # Security & Access Control
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        # Master Data - BOQ Category & Job (Demo data)
        'data/boq_category.csv',
        'data/boq_job.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
