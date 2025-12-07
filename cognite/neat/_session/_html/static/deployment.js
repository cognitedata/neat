let currentFilters = {
    changeType: 'all',
    endpoint: 'all',
    severity: 'all',
};
let currentSearch = '';
const storageKey = 'neat-deployment-theme-' + uniqueId;
let isDarkMode = localStorage.getItem(storageKey) === 'dark';

const container = document.getElementById('deploymentContainer-' + uniqueId);
const themeToggle = document.getElementById('themeToggle-' + uniqueId);
const themeIcon = document.getElementById('themeIcon-' + uniqueId);
const themeText = document.getElementById('themeText-' + uniqueId);

// Status configuration
const STATUS_CONFIG = {
    success: { icon: '✅', text: 'Success' },
    failure: { icon: '❌', text: 'Failure' },
    partial: { icon: '⚠️', text: 'Partial Success' },
    pending: { icon: '⏳', text: 'Pending (Dry Run)' },
    recovered: { icon: '🔄', text: 'Recovered' },
    recovery_failed: { icon: '💔', text: 'Recovery Failed' }
};

// Initialize status badge
function initializeStatus() {
    const statusBadge = document.getElementById('statusBadge-' + uniqueId);
    const statusIcon = document.getElementById('statusIcon-' + uniqueId);
    const statusText = document.getElementById('statusText-' + uniqueId);

    const statusConfig = STATUS_CONFIG[deploymentStatus] || STATUS_CONFIG.pending;
    statusIcon.textContent = statusConfig.icon;
    statusText.textContent = statusConfig.text;
}

function updateTheme() {
    if (isDarkMode) {
        container.classList.add('dark-mode');
        themeIcon.textContent = '☀️';
        themeText.textContent = 'Light';
    } else {
        container.classList.remove('dark-mode');
        themeIcon.textContent = '🌙';
        themeText.textContent = 'Dark';
    }
}

function renderChangeMessage(change) {
    if (!change.message) return '';

    // Using textContent to set the message prevents XSS vulnerabilities
    // by automatically escaping HTML characters.
    const messageHolder = document.createElement('div');
    messageHolder.textContent = change.message;
    const escapedMessage = messageHolder.innerHTML;

    if (change.change_type === 'failed') {
        return `
            <div class="error-message-box">
                <div class="error-message-header">
                    <span class="error-icon">❌</span>
                    <span class="error-title">Deployment Failed</span>
                </div>
                <div class="error-message-content">${escapedMessage}</div>
            </div>`;
    }
    return `
        <div class="info-message-box info-message-${change.change_type}">
            <div class="info-message-content">${escapedMessage}</div>
        </div>`;
}

updateTheme();
initializeStatus();

themeToggle.addEventListener('click', function() {
    isDarkMode = !isDarkMode;
    localStorage.setItem(storageKey, isDarkMode ? 'dark' : 'light');
    updateTheme();
});

function renderChanges() {
    const listContainer = document.getElementById('deploymentList-' + uniqueId);
    const filtered = changes.filter(change => {
        const matchesChangeType = currentFilters.changeType === 'all' ||
                                 change.change_type === currentFilters.changeType;
        const matchesEndpoint = currentFilters.endpoint === 'all' ||
                               change.endpoint === currentFilters.endpoint;
        const matchesSeverity = currentFilters.severity === 'all' ||
                               change.severity === currentFilters.severity;
        const matchesSearch = !currentSearch ||
            change.resource_id.toLowerCase().includes(currentSearch.toLowerCase()) ||
            change.changes.some(fc =>
                fc.field_path.toLowerCase().includes(currentSearch.toLowerCase()) ||
                fc.description.toLowerCase().includes(currentSearch.toLowerCase())
            );
        return matchesChangeType && matchesEndpoint && matchesSeverity && matchesSearch;
    });

    if (filtered.length === 0) {
        listContainer.innerHTML = '<div class="no-changes">No changes match your filters</div>';
        return;
    }

    listContainer.innerHTML = filtered.map(change => `
        <div class="change-item ${change.change_type === 'failed' ? 'failed-change' : ''}">
            <div class="change-header">
                <span class="endpoint-badge endpoint-${change.endpoint}">${change.endpoint}</span>
                <span class="change-type-badge change-${change.change_type}">${change.change_type}</span>
                <span class="severity-badge severity-${change.severity}">${change.severity}</span>
            </div>
            <div class="resource-id">${change.resource_id}</div>

            ${change.changes.length > 0 ? `
                <div class="field-changes">
                    ${change.changes.map(fc => `
                        <div class="field-change">
                            <div class="field-path">${fc.field_path}</div>
                            <div class="field-description">${fc.description}</div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}

            ${renderChangeMessage(change)}

        </div>
    `).join('');
}

// Change type filters (stat items)
document.querySelectorAll('#deploymentContainer-' + uniqueId + ' .stat-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('#deploymentContainer-' + uniqueId + ' .stat-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        currentFilters.changeType = this.dataset.filter;
        renderChanges();
    });
});

// Other filters
document.querySelectorAll('#deploymentContainer-' + uniqueId + ' .filter-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const filterType = this.dataset.filterType;
        document.querySelectorAll('#deploymentContainer-' + uniqueId + ` [data-filter-type="${filterType}"]`).forEach(b =>
            b.classList.remove('active')
        );
        this.classList.add('active');
        currentFilters[filterType] = this.dataset.filter;
        renderChanges();
    });
});

// Search
document.getElementById('searchInput-' + uniqueId).addEventListener('input', function(e) {
    currentSearch = e.target.value;
    renderChanges();
});

// Export function
window['exportDeployment_' + uniqueId] = function() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const report = {
        status: deploymentStatus,
        is_dry_run: is_dry_run === 'True',
        timestamp: timestamp,
        statistics: stats,
        changes: changes,
    };

    const json = JSON.stringify(report, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deployment_report_${timestamp}.json`;
    a.click();
    window.URL.revokeObjectURL(url);
};

renderChanges();