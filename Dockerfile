FROM odoo:19

# Create addons directory
RUN mkdir -p /mnt/extra-addons

# Copy construction_management module
COPY construction_management /mnt/extra-addons/construction_management
COPY combined_workflow_demo.py /tmp/
COPY test_role_workflows.py /tmp/

# Set correct permissions
RUN chown -R odoo:odoo /mnt/extra-addons

EXPOSE 8069

# Run Odoo with construction_management addon
CMD ["odoo", "-i", "construction_management", "--addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons"]
