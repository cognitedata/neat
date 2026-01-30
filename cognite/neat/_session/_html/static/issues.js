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
            // For fixed issues, show "Fixed" badge type
            const badgeType = firstIssue.fixed ? 'Fixed' : firstIssue.type;
            const badgeLabel = firstIssue.fixed ? 'Fixed' : firstIssue.type;
            const fixBoxClass = firstIssue.fixed ? 'issue-fix-applied' : 'issue-fix';
            const fixLabel = firstIssue.fixed ? '✓ Applied Fix' : '💡 Suggested Fix';
            html.push(`
                <div class="issue-item">
                    <div class="issue-header">
                        <span class="issue-badge badge-${badgeType}">${badgeLabel}</span>
                        ${codeLink}
                    </div>
                    <div class="issue-message">${firstIssue.message}</div>
                    ${firstIssue.fix ? `
                        <div class="${fixBoxClass}">
                            <div class="issue-fix-label">${fixLabel}</div>
                            <div class="issue-fix-content">${firstIssue.fix}</div>
                        </div>
                    ` : ''}
                </div>
            `);
        } else {
            // Grouped issues
            // For fixed issues, show "Fixed" badge type
            const badgeType = firstIssue.fixed ? 'Fixed' : firstIssue.type;
            const badgeLabel = firstIssue.fixed ? 'Fixed' : firstIssue.type;
            const fixBoxClass = firstIssue.fixed ? 'issue-fix-applied' : 'issue-fix';
            const fixLabel = firstIssue.fixed ? '✓ Applied Fix' : '💡 Suggested Fix';
            html.push(`
                <div class="issue-group ${isExpanded ? 'expanded' : ''}">
                    <div class="issue-group-header" onclick="toggleGroup_${uniqueId}('${key}')">
                        <div class="issue-group-info">
                            <span class="expand-icon">${isExpanded ? '▼' : '▶'}</span>
                            <span class="issue-badge badge-${badgeType}">${badgeLabel}</span>
                            ${codeLink}
                            <span class="issue-count">${count} fixes</span>
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
                            <div class="${fixBoxClass} grouped">
                                <div class="issue-fix-label">${fixLabel}</div>
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