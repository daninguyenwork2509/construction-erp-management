FROM odoo:19

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy construction_management module
COPY construction_management /mnt/extra-addons/construction_management
COPY combined_workflow_demo.py /tmp/
COPY test_role_workflows.py /tmp/

# Set permissions
RUN chmod -R 777 /mnt/extra-addons/construction_management

EXPOSE 8069

# Entry point - will be set by Railway or docker-compose
CMD ["odoo"]
