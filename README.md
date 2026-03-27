# Construction ERP Management System

Complete Odoo 19 module for construction project management with full workflow support (Lead → Project → BOQ → Quote → PO → Task → VO → Invoice).

## Features

- ✅ 7 User Roles (Admin, Sales, QS, Procurement, Accounting, Site Manager, PM)
- ✅ Bill of Quantities (BOQ) with cost/sale pricing
- ✅ Project Management with Gantt charts & Kanban boards
- ✅ Daily Site Logging with weather, materials, workers tracking
- ✅ Variation Orders with customer approval link + phone verification
- ✅ Quality Control checklists & defect tracking
- ✅ Purchase Order management with vendor integration
- ✅ Full audit trail with mail threading
- ✅ Milestone-based invoicing
- ✅ Cost guardrails & margin shields

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- PostgreSQL 15

### Installation

```bash
# Clone repository
git clone https://github.com/daninguyenwork2509/construction-erp-management.git
cd construction-erp-management

# Start Docker containers
docker-compose up -d

# Run demo data
docker exec construction_app python3 /tmp/combined_workflow_demo.py
```

### Access

- **URL**: http://localhost:8070/odoo
- **Database**: odoo
- **Default Users**: See DEMO_GUIDE.md

## Structure

```
construction_management/
├── models/               # 12 Odoo models
├── views/               # 6 XML view definitions
├── controllers/         # Customer portal routes
├── security/            # Role-based access control
└── data/               # Demo data & security rules
```

## Demo Data

Pre-configured with:
- 7 user roles (all fully functional)
- 2 construction projects
- 13 project tasks
- 2 daily logs
- 2 variation orders (customer approved)
- 1 vendor + customer

See `DEMO_GUIDE.md` for complete testing guide.

## Testing

Run workflow verification:
```bash
docker exec construction_app python3 test_role_workflows.py
```

## Documentation

- `DEMO_GUIDE.md` - Complete customer testing guide with role-by-role workflows
- `construction_management/__manifest__.py` - Module configuration
- Model docstrings - Detailed field & method documentation

## Technical Details

- **Framework**: Odoo 19.0
- **Database**: PostgreSQL 15
- **Language**: Python 3.10
- **Frontend**: HTML/JavaScript (Odoo built-in)

## Compatibility

✅ Odoo 19.0  
✅ Python 3.10+  
✅ PostgreSQL 15+  
✅ Docker & Docker Compose  

## License

Proprietary - BlueBolt Software

## Support

Contact: daninguyenwork2509@gmail.com

---

**Status**: Production-ready for customer demonstrations ✅
