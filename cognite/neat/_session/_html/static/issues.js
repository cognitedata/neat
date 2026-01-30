let currentFilter = 'all';
let currentSearch = '';
const storageKey = 'neat-issues-theme-' + uniqueId;
let isDarkMode = localStorage.getItem(storageKey) === 'dark';
let expandedGroups = new Set();

const container = document.getElementById('issuesContainer-' + uniqueId);
const themeToggle = document.getElementById('themeToggle-' + uniqueId);
const themeIcon = document.getElementById('themeIcon-' + uniqueId);
const themeText = document.getElementById('themeText-' + uniqueId);

// Initialize theme
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

// Theme toggle
themeToggle.addEventListener('click', function() {
    isDarkMode = !isDarkMode;
    localStorage.setItem(storageKey, isDarkMode ? 'dark' : 'light');
    updateTheme();
});

function groupIssues(issuesList) {
    const grouped = new Map();

    issuesList.forEach(issue => {
        const key = issue.code ? `${issue.type}:${issue.code}` : `${issue.type}:${issue.id}`;

        if (!grouped.has(key)) {
            grouped.set(key, []);
        }
        grouped.get(key).push(issue);
    });

    return grouped;
}

function renderFixedIssue(issue) {
    // Render a fixed issue with its list of specific changes
    const items = issue.items || [];
    const hasRelationships = items.some(item => item.source && item.dest);
    
    let itemsHtml = '';
    if (hasRelationships) {
        // Render as relationship list with highlighted container names
        itemsHtml = `
            <ul class="fix-items-list">
                ${items.map(item => {
                    if (item.source && item.dest) {
                        return `<li class="fix-item">
                            <span class="container-name">${item.source}</span>
                            <span class="arrow">→</span>
                            <span class="container-name">${item.dest}</span>
                        </li>`;
                    } else {
                        return `<li class="fix-item">${item.description}</li>`;
                    }
                }).join('')}
            </ul>
        `;
    } else {
        // Render as simple list of descriptions
        itemsHtml = `
            <ul class="fix-items-list">
                ${items.map(item => `<li class="fix-item">${item.description}</li>`).join('')}
            </ul>
        `;
    }
    
    const countLabel = items.length === 1 ? '1 change' : `${items.length} changes`;
    
    return `
        <div class="issue-item fixed-summary">
            <div class="issue-header">
                <span class="issue-badge badge-Fixed">Fixed</span>
                <span class="fix-count">${countLabel}</span>
            </div>
            <div class="issue-message fixed-message">${issue.message}</div>
            ${itemsHtml}
        </div>
    `;
}

function renderIssues() {
    const listContainer = document.getElementById('issuesList-' + uniqueId);
    const filtered = issues.filter(issue => {
        // Handle the "Fixed" filter separately
        if (currentFilter === 'Fixed') {
            // Show only fixed issues
            if (!issue.fixed) return false;
        } else {
            // For all other filters, exclude fixed issues
            if (issue.fixed) return false;
            // Then apply the type filter
            if (currentFilter !== 'all' && issue.type !== currentFilter) return false;
        }
        const matchesSearch = !currentSearch ||
            issue.message.toLowerCase().includes(currentSearch.toLowerCase()) ||
            (issue.code && issue.code.toLowerCase().includes(currentSearch.toLowerCase())) ||
            (issue.fix && issue.fix.toLowerCase().includes(currentSearch.toLowerCase()));
        return matchesSearch;
    });

    if (filtered.length === 0) {
        listContainer.innerHTML = '<div class="no-issues">No issues match your filters</div>';
        return;
    }

    // Check if we're showing fixed issues (they have special rendering)
    if (currentFilter === 'Fixed') {
        const html = filtered.map(issue => renderFixedIssue(issue));
        listContainer.innerHTML = html.join('');
        return;
    }

    const grouped = groupIssues(filtered);
    const html = [];

    grouped.forEach((groupIssues, key) => {
        const firstIssue = groupIssues[0];
        const count = groupIssues.length;
        const isExpanded = expandedGroups.has(key);
        const codeLink = firstIssue.code
            ? `<span class="issue-code-link" onclick="event.stopPropagation(); window.open('https://cognite-neat.readthedocs-hosted.com/en/latest/validation/${firstIssue.code.toLowerCase()}.html', '_blank')">${firstIssue.code}</span>`
            : '';

        if (count === 1) {
            // Single issue - render normally
            html.push(`
                <div class="issue-item">
                    <div class="issue-header">
                        <span class="issue-badge badge-${firstIssue.type}">${firstIssue.type}</span>
                        ${codeLink}
                    </div>
                    <div class="issue-message">${firstIssue.message}</div>
                    ${firstIssue.fix ? `
                        <div class="issue-fix">
                            <div class="issue-fix-label">💡 Suggested Fix</div>
                            <div class="issue-fix-content">${firstIssue.fix}</div>
                        </div>
                    ` : ''}
                </div>
            `);
        } else {
            // Grouped issues
            html.push(`
                <div class="issue-group ${isExpanded ? 'expanded' : ''}">
                    <div class="issue-group-header" onclick="toggleGroup_${uniqueId}('${key}')">
                        <div class="issue-group-info">
                            <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                            <span class="issue-badge badge-${firstIssue.type}">${firstIssue.type}</span>
                            ${codeLink}
                            <span class="issue-count">${count} issues</span>
                        </div>
                    </div>
                    <div class="issue-group-items">
                        ${groupIssues.map((issue, idx) => `
                            <div class="issue-item grouped">
                                <div class="issue-number">#${idx + 1}</div>
                                <div class="issue-message">${issue.message}</div>
                            </div>
                        `).join('')}
                        ${firstIssue.fix ? `
                            <div class="issue-fix grouped">
                                <div class="issue-fix-label">💡 Suggested Fix</div>
                                <div class="issue-fix-content">${firstIssue.fix}</div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `);
        }
    });

    listContainer.innerHTML = html.join('');
}

window['toggleGroup_' + uniqueId] = function(key) {
    if (expandedGroups.has(key)) {
        expandedGroups.delete(key);
    } else {
        expandedGroups.add(key);
    }
    renderIssues();
};

// Stat item filters
document.querySelectorAll('#issuesContainer-' + uniqueId + ' .stat-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('#issuesContainer-' + uniqueId + ' .stat-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        currentFilter = this.dataset.filter;
        renderIssues();
    });
});

// Search
document.getElementById('searchInput-' + uniqueId).addEventListener('input', function(e) {
    currentSearch = e.target.value;
    renderIssues();
});

// Export function
window['exportIssues_' + uniqueId] = function() {
    const csv = [
        ['Type', 'Code', 'Message', 'Fix'],
        ...issues.map(i => [i.type, i.code || '', i.message, i.fix || ''])
    ].map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'session_issues.csv';
    a.click();
    window.URL.revokeObjectURL(url);
};

renderIssues();