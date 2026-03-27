#!/usr/bin/env python3
"""
Test Construction ERP - Verify each role workflow
Login & test as: Admin, Sales, QS, Procurement, Accounting, Site Manager, PM
"""
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import odoo
from odoo.api import Environment
from odoo.modules.registry import Registry
from odoo.tools import config

# Setup Odoo
config['db_host'] = 'db'
config['db_user'] = 'odoo'
config['db_password'] = 'odoo'
config['db_name'] = 'odoo'
config['addons_path'] = '/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons'

print("\n" + "="*70)
print("CONSTRUCTION ERP - ROLE WORKFLOW VERIFICATION")
print("="*70)

registry = Registry.new('odoo', update_module=False)

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})

    # Get base data
    users = env['res.users'].search([('login', '!=', 'public')])
    projects = env['sale.order'].search([('name', 'ilike', 'Demo Project')])
    customer = env['res.partner'].search([('name', '=', 'BlueBolt Client Demo')], limit=1)

    print(f"\n✓ Base Data Loaded:")
    print(f"  - {len(users)} users")
    print(f"  - {len(projects)} projects")
    print(f"  - 1 customer: {customer.name if customer else 'None'}")

    # Test each role
    print("\n" + "="*70)
    print("[1/7] ADMIN ROLE - System Administration")
    print("="*70)
    admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)
    if admin_user:
        print(f"✓ Admin user: {admin_user.name}")
        print(f"  - Email: {admin_user.email}")
        print(f"  - Groups: {', '.join([g.name for g in admin_user.group_ids])}")

    print("\n" + "="*70)
    print("[2/7] SALES ROLE - Lead Management & Quote")
    print("="*70)
    sales_user = env['res.users'].search([('login', '=', 'sales01')], limit=1)
    if sales_user:
        print(f"✓ Sales user: {sales_user.name}")
        # Check projects assigned to sales
        sales_projects = projects.filtered(lambda p: p.user_id.id == sales_user.id)
        print(f"  - Assigned projects: {len(sales_projects)}")
        for proj in sales_projects[:2]:
            print(f"    • {proj.name} - {proj.state} (Amount: {proj.amount_total:,.0f})")

    print("\n" + "="*70)
    print("[3/7] QS ROLE - Bill of Quantities & Margin Shield")
    print("="*70)
    qs_user = env['res.users'].search([('login', '=', 'qs01')], limit=1)
    if qs_user:
        print(f"✓ QS user: {qs_user.name}")
        # Check BOQ structure
        boq_categories = env['boq.category'].search([])
        boq_jobs = env['boq.job'].search([])
        print(f"  - BOQ Categories: {len(boq_categories)}")
        print(f"  - BOQ Jobs: {len(boq_jobs)}")
        if boq_jobs:
            for job in boq_jobs[:3]:
                print(f"    • {job.name}: Cost {job.cost_price:,.0f} → Sale {job.sale_price:,.0f}")

    print("\n" + "="*70)
    print("[4/7] PROCUREMENT ROLE - Purchase Orders & Vendor Management")
    print("="*70)
    procurement_user = env['res.users'].search([('login', '=', 'procurement01')], limit=1)
    if procurement_user:
        print(f"✓ Procurement user: {procurement_user.name}")
        # Check vendors
        vendors = env['res.partner'].search([('supplier_rank', '>', 0)])
        print(f"  - Vendors: {len(vendors)}")
        for vendor in vendors[:3]:
            print(f"    • {vendor.name}")
        # Check POs
        pos = env['purchase.order'].search([])
        print(f"  - Purchase Orders: {len(pos)}")
        for po in pos[:3]:
            print(f"    • PO {po.name}: {po.state} ({len(po.order_line)} lines)")

    print("\n" + "="*70)
    print("[5/7] SITE MANAGER ROLE - Daily Logs, Tasks & QC Checklists")
    print("="*70)
    siteman_user = env['res.users'].search([('login', '=', 'siteman01')], limit=1)
    if siteman_user:
        print(f"✓ Site Manager user: {siteman_user.name}")
        # Check daily logs
        daily_logs = env['daily.log'].search([])
        print(f"  - Daily Logs: {len(daily_logs)}")
        for log in daily_logs[:2]:
            print(f"    • {log.name} ({log.date}): {log.state} - {log.workers_count} workers")

        # Check tasks
        tasks = env['project.task'].search([])
        print(f"  - Project Tasks: {len(tasks)}")
        for task in tasks[:3]:
            progress = f"{task.progress or 0}%" if hasattr(task, 'progress') else "N/A"
            print(f"    • {task.name} [{progress}] in {task.project_id.name}")

        # Check QC checklists
        qc_checklists = env['qc.checklist'].search([])
        print(f"  - QC Checklists: {len(qc_checklists)}")
        for qc in qc_checklists[:2]:
            print(f"    • {qc.name}: {qc.state} ({qc.pass_percentage:.0f}% pass)")

    print("\n" + "="*70)
    print("[6/7] PM ROLE - Project Management & VO Approval")
    print("="*70)
    pm_user = env['res.users'].search([('login', '=', 'pm01')], limit=1)
    if pm_user:
        print(f"✓ PM user: {pm_user.name}")
        # Check assigned projects
        pm_projects = projects.filtered(lambda p: p.pm_id.id == pm_user.id)
        print(f"  - Assigned Projects: {len(pm_projects)}")
        for proj in pm_projects[:2]:
            print(f"    • {proj.name} - {proj.construction_type}")

        # Check VOs
        vos = env['variation.order'].search([])
        print(f"  - Variation Orders: {len(vos)}")
        for vo in vos[:3]:
            print(f"    • VO {vo.name}: {vo.state} ({vo.change_amount:,.0f} change)")

    print("\n" + "="*70)
    print("[7/7] ACCOUNTING ROLE - Milestone & Invoice Management")
    print("="*70)
    accounting_user = env['res.users'].search([('login', '=', 'accounting01')], limit=1)
    if accounting_user:
        print(f"✓ Accounting user: {accounting_user.name}")
        # Check invoices
        invoices = env['account.move'].search([('move_type', '=', 'out_invoice')])
        print(f"  - Invoices: {len(invoices)}")
        for inv in invoices[:3]:
            print(f"    • {inv.name}: {inv.state} ({inv.amount_total:,.0f})")

        # Check payments
        payments = env['account.move'].search([('move_type', '=', 'entry')])
        print(f"  - Payment Records: {len(payments)}")

print("\n" + "="*70)
print("✅ WORKFLOW VERIFICATION COMPLETE")
print("="*70)
print("""
NEXT STEPS - Manual Testing via Browser:
1. Open: http://localhost:8070/odoo
2. Login as each role (password = username):
   - admin / admin
   - sales01 / sales01
   - qs01 / qs01
   - procurement01 / procurement01
   - accounting01 / accounting01
   - siteman01 / siteman01
   - pm01 / pm01

3. Test each workflow:
   ✓ Sales: Create Lead → Convert to Quote → Approve
   ✓ QS: View BOQ, check Margin Shield
   ✓ Procurement: Create PO, check vendor prices
   ✓ Site Manager: Update daily log, task progress, create QC checklist
   ✓ PM: View Gantt, approve VO, milestone tracking
   ✓ Accounting: Process milestone receipt, create invoice
   ✓ Admin: View executive dashboard, manage users/groups
""")
print("="*70 + "\n")
