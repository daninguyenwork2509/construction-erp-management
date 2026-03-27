FROM odoo:19

# Copy construction_management module
COPY --chown=odoo:odoo construction_management /mnt/extra-addons/construction_management
COPY --chown=odoo:odoo combined_workflow_demo.py /tmp/
COPY --chown=odoo:odoo test_role_workflows.py /tmp/

EXPOSE 8069

# Run Odoo with construction_management addon
CMD ["odoo", "-i", "construction_management", "--addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons"]
