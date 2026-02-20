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

function renderFixedIssueContent(issue) {
    // Render just the content part of a fixed issue (for use in grouped items)
    if (issue.fix_type === 'constraint' && issue.source_name && issue.dest_name) {
        // Fancy rendering for constraint fixes
        const isRemove = issue.action_type === 'remove';
        const itemClass = isRemove ? 'fix-item fix-item-remove' : 'fix-item fix-item-add';
        const actionIcon = isRemove ? '×' : '✓';
        const arrowSymbol = '→';
        const constraintId = issue.constraint_id || '';
        const fullPath = constraintId ? `${issue.source_name}.constraints.${constraintId}` : '';

        return `
            <div class="${itemClass}">
                <span class="fix-action-icon">${actionIcon}</span>
                <span class="container-name">${issue.source_name}</span>
                <span class="constraint-arrow-symbol">${arrowSymbol}</span>
                <span class="container-name">${issue.dest_name}</span>
                <span class="fix-identifier">${fullPath}</span>
            </div>
        `;
    } else if (issue.fix_type === 'index' && issue.container_name && issue.property_id) {
        // Fancy rendering for index fixes
        const indexId = issue.index_id || '';
        const fullPath = indexId ? `${issue.container_name}.indexes.${indexId}` : '';
        const isChange = issue.action_type === 'change';
        const modifiedTag = isChange ? '<span class="modified-tag">(modified existing)</span>' : '';
        return `
            <div class="fix-item fix-item-add">
                <span class="fix-action-icon">✓</span>
                <span class="container-name">${issue.container_name}</span>
                <span class="property-dot">.</span>
                <span class="property-name">${issue.property_id}</span>
                ${modifiedTag}
                <span class="fix-identifier">${fullPath}</span>
            </div>
        `;
    } else {
        // No fancy rendering available - content is empty (message shown separately)
        return '';
    }
}

function matchesSearch(item) {
    if (!currentSearch) return true;
    const searchLower = currentSearch.toLowerCase();
    return item.message.toLowerCase().includes(searchLower) ||
        (item.code && item.code.toLowerCase().includes(searchLower)) ||
        (item.fix && item.fix.toLowerCase().includes(searchLower));
}

function renderIssues() {
    const listContainer = document.getElementById('issuesList-' + uniqueId);

    const isFixedTab = currentFilter === 'Fixed';
    const source = isFixedTab ? fixes : issues;
    const filtered = source.filter(item => {
        if (!isFixedTab && currentFilter !== 'all' && item.type !== currentFilter) return false;
        return matchesSearch(item);
    });

    if (filtered.length === 0) {
        if (isFixedTab) {
            if (fixes.length > 0 && currentSearch) {
                listContainer.innerHTML = '<div class="no-issues">No fixes match your filters</div>';
            } else if (fixableCount > 0) {
                listContainer.innerHTML = `<div class="no-issues"><div style="margin-bottom: 16px; text-align: center;">No fixes have been applied yet. <strong>${fixableCount} issue${fixableCount === 1 ? '' : 's'} can be automatically fixed.</strong></div><div class="info-box"><span class="info-icon">💡</span><div>Read your data model with <code style="background: rgba(128, 128, 128, 0.15); padding: 2px 6px; border-radius: 3px; font-family: monospace; color: var(--text-primary);">fix=True</code> to automatically fix common issues.</div></div></div>`;
            } else {
                listContainer.innerHTML = '<div class="no-issues">No issues can be automatically fixed.</div>';
            }
        } else {
            listContainer.innerHTML = '<div class="no-issues">No issues match your filters</div>';
        }
        return;
    }

    // Check if we're showing fixed issues (they use same grouping as regular issues)
    if (currentFilter === 'Fixed') {
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
                // Single fix - render with message and fancy UI
                html.push(`
                    <div class="issue-item">
                        <div class="issue-header">
                            <span class="issue-badge badge-Fixed">Fixed</span>
                            ${codeLink}
                        </div>
                        <div class="issue-fix-applied">
                            <div class="issue-fix-label">✓ Applied Fix</div>
                            <div class="issue-fix-content">${firstIssue.message}</div>
                        </div>
                        ${renderFixedIssueContent(firstIssue)}
                    </div>
                `);
            } else {
                // Grouped fixes - show message once at top
                html.push(`
                    <div class="issue-group ${isExpanded ? 'expanded' : ''}">
                        <div class="issue-group-header" onclick="toggleGroup_${uniqueId}('${key}')">
                            <div class="issue-group-info">
                                <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                                <span class="issue-badge badge-Fixed">Fixed</span>
                                ${codeLink}
                                <span class="issue-count">${count} fixes</span>
                            </div>
                        </div>
                        <div class="issue-group-items">
                            <div class="issue-fix-applied grouped">
                                <div class="issue-fix-label">✓ Applied Fix</div>
                                <div class="issue-fix-content">${firstIssue.message}</div>
                            </div>
                            ${groupIssues.map((issue) => {
                                const content = renderFixedIssueContent(issue);
                                const fixClass = issue.action_type === 'remove' ? ' fix-remove' : ' fix-add';
                                return `
                                    <div class="issue-item grouped${fixClass}">
                                        ${content}
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `);
            }
        });

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

        const fixableBadge = firstIssue.fixable
            ? '<span class="issue-badge badge-AutoFixable">Automatically fixable</span>'
            : '';

        if (count === 1) {
            // Single issue - render normally
            html.push(`
                <div class="issue-item">
                    <div class="issue-header">
                        <span class="issue-badge badge-${firstIssue.type}">${firstIssue.type}</span>
                        ${fixableBadge}
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
                            ${fixableBadge}
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
        ...issues.concat(fixes).map(i => [i.type, i.code || '', i.message, i.fix || ''])
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
