let currentFilter = 'all';
let currentSearch = '';
let isDarkMode = localStorage.getItem('neat-issues-theme') === 'dark';

const container = document.getElementById('issuesContainer');
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const themeText = document.getElementById('themeText');

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
    localStorage.setItem('neat-issues-theme', isDarkMode ? 'dark' : 'light');
    updateTheme();
});

function renderIssues() {
    const listContainer = document.getElementById('issuesList');
    const filtered = issues.filter(issue => {
        const matchesFilter = currentFilter === 'all' || issue.type === currentFilter;
        const matchesSearch = !currentSearch ||
            issue.message.toLowerCase().includes(currentSearch.toLowerCase()) ||
            (issue.code && issue.code.toLowerCase().includes(currentSearch.toLowerCase())) ||
            (issue.fix && issue.fix.toLowerCase().includes(currentSearch.toLowerCase()));
        return matchesFilter && matchesSearch;
    });

    if (filtered.length === 0) {
        listContainer.innerHTML = '<div class="no-issues">No issues match your filters</div>';
        return;
    }

    listContainer.innerHTML = filtered.map(issue => `
        <div class="issue-item">
            <div class="issue-header">
                <span class="issue-badge badge-${issue.type}">${issue.type}</span>
                ${issue.code ? `<span class="issue-code">${issue.code}</span>` : ''}
            </div>
            <div class="issue-message">${issue.message}</div>
            ${issue.fix ? `
                <div class="issue-fix">
                    <div class="issue-fix-label">💡 Suggested Fix</div>
                    <div class="issue-fix-content">${issue.fix}</div>
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Stat item filters
document.querySelectorAll('.stat-item').forEach(item => {
    item.addEventListener('click', function() {
        document.querySelectorAll('.stat-item').forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        currentFilter = this.dataset.filter;
        renderIssues();
    });
});

// Search
document.getElementById('searchInput').addEventListener('input', function(e) {
    currentSearch = e.target.value;
    renderIssues();
});

// Export function
window.exportIssues = function() {
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