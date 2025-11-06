import json
from collections import defaultdict
from typing import Any

from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation
from cognite.neat._store import NeatStore

from ._shared import HTML_STYLE


class Issues:
    """Class to handle issues in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    @property
    def _issues(self) -> IssueList:
        """Get all issues from the last change in the store."""
        issues = IssueList()
        if change := self._store.provenance.last_change:
            issues += change.errors or IssueList()
            issues += change.issues or IssueList()
        return issues

    @property
    def _stats(self) -> dict[str, Any]:
        """Compute statistics about issues."""
        by_type: defaultdict[str, int] = defaultdict(int)
        by_code: defaultdict[str, int] = defaultdict(int)

        stats: dict[str, Any] = {
            "total": len(self._issues),
            "by_type": by_type,
            "by_code": by_code,
            "severity_order": [ModelSyntaxError.__name__, ConsistencyError.__name__, Recommendation.__name__],
        }

        for issue in self._issues:
            stats["by_type"][issue.issue_type()] += 1

            if issue.code:
                stats["by_code"][f"{issue.issue_type()}:{issue.code}"] += 1

        return stats

    @property
    def _serialized_issues(self) -> list[dict[str, Any]]:
        """Convert issues to JSON-serializable format."""
        serialized = []
        for idx, issue in enumerate(self._issues):
            serialized.append(
                {
                    "id": idx,
                    "type": issue.issue_type(),
                    "code": issue.code or "",
                    "message": issue.message,
                    "fix": issue.fix or "",
                }
            )
        return serialized

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        issues_json = json.dumps(self._serialized_issues)

        html = f"""
        {HTML_STYLE}
        <div class="issues-container" id="issuesContainer">
            <div class="issues-header">
                <button class="theme-toggle" id="themeToggle">
                    <span id="themeIcon">🌙</span>
                    <span id="themeText">Dark</span>
                </button>
                <h2 class="issues-title">Session Issues</h2>
                <div class="issues-stats">
                    <div class="stat-item active" data-filter="all">
                        <span class="stat-number">{self._stats["total"]}</span> Total Issues
                    </div>
                    <div class="stat-item" data-filter="ModelSyntaxError">
                    <span class="stat-number">{self._stats["by_type"].get("ModelSyntaxError", 0)}</span> Syntax Errors
                    </div>
                    <div class="stat-item" data-filter="ConsistencyError">
                <span class="stat-number">{self._stats["by_type"].get("ConsistencyError", 0)}</span> Consistency Errors
                    </div>
                    <div class="stat-item" data-filter="Recommendation">
                <span class="stat-number">{self._stats["by_type"].get("Recommendation", 0)}</span> Recommendations
                    </div>
                    <button class="export-btn" onclick="exportIssues()">Export CSV</button>
                </div>
            </div>

            <div class="issues-controls">
                <div class="control-group">
            <input type="text" class="search-input" placeholder="🔍 Search messages, codes, fixes..." id="searchInput">
                </div>
            </div>

            <div class="issues-list" id="issuesList"></div>
        </div>

        <script>
            (function() {{
                const issues = {issues_json};
                let currentFilter = 'all';
                let currentSearch = '';
                let isDarkMode = localStorage.getItem('neat-issues-theme') === 'dark';

                const container = document.getElementById('issuesContainer');
                const themeToggle = document.getElementById('themeToggle');
                const themeIcon = document.getElementById('themeIcon');
                const themeText = document.getElementById('themeText');

                // Initialize theme
                function updateTheme() {{
                    if (isDarkMode) {{
                        container.classList.add('dark-mode');
                        themeIcon.textContent = '☀️';
                        themeText.textContent = 'Light';
                    }} else {{
                        container.classList.remove('dark-mode');
                        themeIcon.textContent = '🌙';
                        themeText.textContent = 'Dark';
                    }}
                }}

                updateTheme();

                // Theme toggle
                themeToggle.addEventListener('click', function() {{
                    isDarkMode = !isDarkMode;
                    localStorage.setItem('neat-issues-theme', isDarkMode ? 'dark' : 'light');
                    updateTheme();
                }});

                function renderIssues() {{
                    const listContainer = document.getElementById('issuesList');
                    const filtered = issues.filter(issue => {{
                        const matchesFilter = currentFilter === 'all' || issue.type === currentFilter;
                        const matchesSearch = !currentSearch ||
                            issue.message.toLowerCase().includes(currentSearch.toLowerCase()) ||
                            (issue.code && issue.code.toLowerCase().includes(currentSearch.toLowerCase())) ||
                            (issue.fix && issue.fix.toLowerCase().includes(currentSearch.toLowerCase()));
                        return matchesFilter && matchesSearch;
                    }});

                    if (filtered.length === 0) {{
                        listContainer.innerHTML = '<div class="no-issues">No issues match your filters</div>';
                        return;
                    }}

                    listContainer.innerHTML = filtered.map(issue => `
                        <div class="issue-item">
                            <div class="issue-header">
                                <span class="issue-badge badge-${{issue.type}}">${{issue.type}}</span>
                                ${{issue.code ? `<span class="issue-code">${{issue.code}}</span>` : ''}}
                            </div>
                            <div class="issue-message">${{issue.message}}</div>
                            ${{issue.fix ? `
                                <div class="issue-fix">
                                    <div class="issue-fix-label">💡 Suggested Fix</div>
                                    <div class="issue-fix-content">${{issue.fix}}</div>
                                </div>
                            ` : ''}}
                        </div>
                    `).join('');
                }}

                // Stat item filters
                document.querySelectorAll('.stat-item').forEach(item => {{
                    item.addEventListener('click', function() {{
                        document.querySelectorAll('.stat-item').forEach(i => i.classList.remove('active'));
                        this.classList.add('active');
                        currentFilter = this.dataset.filter;
                        renderIssues();
                    }});
                }});

                // Search
                document.getElementById('searchInput').addEventListener('input', function(e) {{
                    currentSearch = e.target.value;
                    renderIssues();
                }});

                // Export function
                window.exportIssues = function() {{
                    const csv = [
                        ['Type', 'Code', 'Message', 'Fix'],
                        ...issues.map(i => [i.type, i.code || '', i.message, i.fix || ''])
                    ].map(row => row.map(cell => `"${{String(cell).replace(/"/g, '""')}}"`).join(',')).join('\\n');

                    const blob = new Blob([csv], {{ type: 'text/csv' }});
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'session_issues.csv';
                    a.click();
                    window.URL.revokeObjectURL(url);
                }};

                renderIssues();
            }})();
        </script>
        """

        return html
