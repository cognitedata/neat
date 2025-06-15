import html
from datetime import datetime

from IPython.display import HTML

from cognite.neat.core._client.data_classes.deploy_result import (
    DeployResult,
)


def display_deploy_result(deploy_result: DeployResult) -> HTML:
    """
    Display a DeployResult instance as formatted HTML in a Jupyter notebook.

    Args:
        deploy_result: The DeployResult instance to display
    """

    # Helper function to safely convert objects to strings
    def safe_str(obj: object) -> str:
        return html.escape(str(obj))

    # Calculate aggregated statistics
    total_created = len(deploy_result.created)
    total_updated = len(deploy_result.updated)
    total_deleted = len(deploy_result.deleted)
    total_skipped = len(deploy_result.skipped) + len(deploy_result.unchanged) + len(deploy_result.existing)
    total_failed = (
        len(deploy_result.failed_created)
        + len(deploy_result.failed_deleted)
        + len(deploy_result.failed_updated)
        + len(deploy_result.failed_restored)
    )

    # Determine status styling
    status_class = deploy_result.status.replace("-", "_")
    status_text = deploy_result.status.upper().replace("-", " ")

    # Create lists for display
    created_items = [safe_str(item) for item in deploy_result.created]

    # Extract resource IDs from updated ResourceDifference objects
    updated_items = []
    for diff in deploy_result.updated:
        updated_items.append(safe_str(diff.resource_id))

    deleted_items = [safe_str(item) for item in deploy_result.deleted]

    # Combine all failed operations with proper error handling
    failed_operations = []
    for failed in deploy_result.failed_created:
        resources = ", ".join([safe_str(rid) for rid in failed.resource_ids]) if failed.resource_ids else "Unknown"
        failed_operations.append(f"Create [{failed.status_code}]: {resources} - {safe_str(failed.error_message)}")

    for failed in deploy_result.failed_deleted:
        resources = ", ".join([safe_str(rid) for rid in failed.resource_ids]) if failed.resource_ids else "Unknown"
        failed_operations.append(f"Delete [{failed.status_code}]: {resources} - {safe_str(failed.error_message)}")

    for failed in deploy_result.failed_updated:
        resources = ", ".join([safe_str(rid) for rid in failed.resource_ids]) if failed.resource_ids else "Unknown"
        failed_operations.append(f"Update [{failed.status_code}]: {resources} - {safe_str(failed.error_message)}")

    for failed in deploy_result.failed_restored:
        resources = ", ".join([safe_str(rid) for rid in failed.resource_ids]) if failed.resource_ids else "Unknown"
        failed_operations.append(f"Restore [{failed.status_code}]: {resources} - {safe_str(failed.error_message)}")

    # Add forced resources information
    forced_items = []
    for forced in deploy_result.forced:
        forced_items.append(f"{safe_str(forced.resource_id)} - {safe_str(forced.reason)}")

    # Create detailed diff information for updates
    update_details = []
    for diff in deploy_result.updated:
        if diff:  # Check if there are actual differences
            changes = []
            for prop in diff.added:
                changes.append(f"+ {prop.location}: {prop.value_representation or 'N/A'}")
            for prop in diff.removed:
                changes.append(f"- {prop.location}: {prop.value_representation or 'N/A'}")
            for prop in diff.changed:
                changes.append(
                    f"~ {prop.location}: {prop.previous_representation or 'N/A'} → {prop.value_representation or 'N/A'}"
                )

            if changes:
                update_details.append(
                    {
                        "resource_id": safe_str(diff.resource_id),
                        "changes": changes[:5],  # Limit to first 5 changes for display
                    }
                )

    # Generate current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    resource_type = deploy_result.resource_type or "Resources"
    # Create HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Deployment Result</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            .deploy-container {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 16px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                backdrop-filter: blur(10px);
                margin: 20px 0;
            }}

            .header {{
                padding: 30px;
                background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
                color: white;
                position: relative;
                overflow: hidden;
            }}

            .header::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grid" width="10" height="10"  patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="0.5"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
                opacity: 0.3;
            }}

            .header-content {{
                position: relative;
                z-index: 1;
            }}

            .status-badge {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 600;
                font-size: 14px;
                margin-bottom: 15px;
                animation: pulse 2s infinite;
            }}

            .status-success {{
                background: rgba(72, 187, 120, 0.2);
                color: #38a169;
                border: 2px solid rgba(72, 187, 120, 0.3);
            }}

            .status-failure {{
                background: rgba(245, 101, 101, 0.2);
                color: #e53e3e;
                border: 2px solid rgba(245, 101, 101, 0.3);
            }}

            .status-dry_run {{
                background: rgba(237, 137, 54, 0.2);
                color: #dd6b20;
                border: 2px solid rgba(237, 137, 54, 0.3);
            }}

            .status-icon {{
                width: 16px;
                height: 16px;
                border-radius: 50%;
            }}

            .success-icon {{ background: #38a169; }}
            .failure-icon {{ background: #e53e3e; }}
            .dry_run-icon {{ background: #dd6b20; }}

            h1 {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 10px;
            }}

            .message {{
                font-size: 1.1rem;
                opacity: 0.9;
            }}

            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                padding: 30px;
                background: rgba(255, 255, 255, 0.95);
            }}

            .stat-card {{
                background: white;
                padding: 24px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                border-left: 4px solid;
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }}

            .stat-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            }}

            .stat-card::before {{
                content: '';
                position: absolute;
                top: 0;
                right: 0;
                width: 40px;
                height: 40px;
                background: linear-gradient(45deg, rgba(0,0,0,0.05), transparent);
                border-radius: 0 0 0 40px;
            }}

            .stat-number {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}

            .stat-label {{
                font-size: 0.9rem;
                color: #64748b;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            .create-card {{ border-left-color: #10b981; }}
            .update-card {{ border-left-color: #3b82f6; }}
            .delete-card {{ border-left-color: #ef4444; }}
            .skip-card {{ border-left-color: #6b7280; }}
            .fail-card {{ border-left-color: #f59e0b; }}

            .details-section {{
                padding: 30px;
                background: rgba(255, 255, 255, 0.95);
            }}

            .section-title {{
                font-size: 1.5rem;
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #e2e8f0;
            }}

            .details-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                margin-top: 20px;
            }}

            .detail-card {{
                background: #f8fafc;
                border-radius: 8px;
                padding: 20px;
                border: 1px solid #e2e8f0;
            }}

            .detail-title {{
                font-weight: 600;
                color: #4a5568;
                margin-bottom: 12px;
                font-size: 1.1rem;
            }}

            .resource-list {{
                max-height: 200px;
                overflow-y: auto;
                scrollbar-width: thin;
            }}

            .resource-item {{
                padding: 8px 12px;
                background: white;
                margin-bottom: 6px;
                border-radius: 6px;
                border-left: 3px solid #cbd5e0;
                font-size: 0.9rem;
                transition: all 0.2s ease;
            }}

            .resource-item:hover {{
                background: #edf2f7;
                border-left-color: #667eea;
            }}

            .update-item {{
                padding: 12px;
            }}

            .resource-name {{
                font-weight: 600;
                margin-bottom: 8px;
                color: #2d3748;
            }}

            .property-changes {{
                margin-left: 12px;
            }}

            .property-change {{
                font-size: 0.8rem;
                padding: 2px 8px;
                margin: 2px 0;
                border-radius: 4px;
                font-family: 'Monaco', 'Consolas', monospace;
            }}

            .property-change.added {{
                background-color: #f0fff4;
                color: #22543d;
                border-left: 2px solid #38a169;
            }}

            .property-change.removed {{
                background-color: #fff5f5;
                color: #742a2a;
                border-left: 2px solid #e53e3e;
            }}

            .property-change.modified {{
                background-color: #fffbf0;
                color: #744210;
                border-left: 2px solid #dd6b20;
            }}

            .empty-state {{
                text-align: center;
                color: #a0aec0;
                font-style: italic;
                padding: 20px;
            }}

            .footer {{
                background: #2d3748;
                color: white;
                padding: 20px 30px;
                text-align: center;
                font-size: 0.9rem;
                opacity: 0.8;
            }}

            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.8; }}
            }}
        </style>
    </head>
    <body>
        <div class="deploy-container">
            <div class="header">
                <div class="header-content">
                    <div class="status-badge status-{status_class}">
                        <div class="status-icon {status_class}-icon"></div>
                        {status_text}
                    </div>
                    <h1>{resource_type} Deployment Result</h1>
                    <div class="message">{
        safe_str(deploy_result.message) if deploy_result.message else "No message provided"
    }</div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card create-card">
                    <div class="stat-number">{total_created}</div>
                    <div class="stat-label">{resource_type} Created</div>
                </div>

                <div class="stat-card update-card">
                    <div class="stat-number">{total_updated}</div>
                    <div class="stat-label">{resource_type} Updated</div>
                </div>

                <div class="stat-card delete-card">
                    <div class="stat-number">{total_deleted}</div>
                    <div class="stat-label">{resource_type} Deleted</div>
                </div>

                <div class="stat-card skip-card">
                    <div class="stat-number">{total_skipped}</div>
                    <div class="stat-label">{resource_type} Skipped</div>
                </div>

                <div class="stat-card fail-card">
                    <div class="stat-number">{total_failed}</div>
                    <div class="stat-label">Failed Operations</div>
                </div>
            </div>

            <div class="details-section">
                <h2 class="section-title">Operation Details</h2>

                <div class="details-grid">
                    <div class="detail-card">
                        <div class="detail-title">Successfully Created</div>
                        <div class="resource-list">
                            {_generate_resource_list(created_items)}
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-title">Successfully Updated</div>
                        <div class="resource-list">
                            {_generate_update_details(update_details)}
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-title">Successfully Deleted</div>
                        <div class="resource-list">
                            {_generate_resource_list(deleted_items)}
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-title">Failed Operations</div>
                        <div class="resource-list">
                            {_generate_resource_list(failed_operations)}
                        </div>
                    </div>

                    {
        ""
        if not forced_items
        else f'''
                    <div class="detail-card">
                        <div class="detail-title">Forced Resources</div>
                        <div class="resource-list">
                            {_generate_resource_list(forced_items)}
                        </div>
                    </div>
                    '''
    }
                </div>
            </div>

            <div class="footer">
                Deployment completed at {timestamp} | {
        "Restoration Enabled" if deploy_result.restored else "Standard Deployment"
    }
            </div>
        </div>
    </body>
    </html>
    """  # noqa: E501

    # Display the HTML in Jupyter
    return HTML(html_content)


def _generate_resource_list(items: list) -> str:
    """Helper function to generate HTML for resource lists."""
    if not items:
        return '<div class="empty-state">No items</div>'

    html_items = []
    for item in items:
        html_items.append(f'<div class="resource-item">{item}</div>')

    return "".join(html_items)


def _generate_update_details(update_details: list) -> str:
    """Helper function to generate HTML for update details with property changes."""
    if not update_details:
        return '<div class="empty-state">No items</div>'

    html_items = []
    for detail in update_details:
        # Create a collapsible item for each updated resource
        changes_html = '<div class="property-changes">'
        for change in detail["changes"]:
            change_class = "added" if change.startswith("+") else "removed" if change.startswith("-") else "modified"
            changes_html += f'<div class="property-change {change_class}">{change}</div>'
        changes_html += "</div>"

        html_items.append(f"""
            <div class="resource-item update-item">
                <div class="resource-name">{detail["resource_id"]}</div>
                {changes_html}
            </div>
        """)

    return "".join(html_items)
