let currentFilters = {
    changeType: 'all',
    endpoint: 'all',
    severity: 'all',
};
let currentSearch = '';
let isDarkMode = localStorage.getItem('neat-deployment-theme') === 'dark';

const container = document.getElementById('deploymentContainer');
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const themeText = document.getElementById('themeText');

// Status configuration
const STATUS_CONFIG = {
    success: { icon: '✅', text: 'Success' },
    failure: { icon: '❌', text: 'Failure' },
    partial: { icon: '⚠️', text: 'Partial Success' },
    pending: { icon: '⏳', text: 'Pending (Dry Run)' }
};

// Initialize status badge
function initializeStatus() {
    const statusBadge = document.getElementById('statusBadge');
    const statusIcon = document.getElementById('statusIcon');
    const statusText = document.getElementById('statusText');

    const statusConfig = STATUS_CONFIG[stats.status] || STATUS_CONFIG.pending;
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

updateTheme();
initializeStatus();

themeToggle.addEventListener('click', function() {
    isDarkMode = !isDarkMode;
    localStorage.setItem('neat-deployment-theme', isDarkMode ? 'dark' : 'light');
    updateTheme();
});

function renderChanges() {
    const listContainer = document.getElementById('deploymentList');
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
        <div class="change-item">
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
        </div>
    `).join('');
}

// Change type filters (stat items)
document.querySelectorAll('.stat-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('.stat-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        currentFilters.changeType = this.dataset.filter;
        renderChanges();
    });
});

// Other filters
document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const filterType = this.dataset.filterType;
        document.querySelectorAll(`[data-filter-type="${filterType}"]`).forEach(b =>
            b.classList.remove('active')
        );
        this.classList.add('active');
        currentFilters[filterType] = this.dataset.filter;
        renderChanges();
    });
});

// Search
document.getElementById('searchInput').addEventListener('input', function(e) {
    currentSearch = e.target.value;
    renderChanges();
});

// Export function
window.exportDeployment = function() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const report = {
        status: stats.status,
        is_dry_run: stats.is_dry_run,
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