import json
from collections import defaultdict
from typing import Any

from cognite.neat._issues import IssueList
from cognite.neat._store import NeatStore


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
            "severity_order": ["ModelSyntaxError", "ConsistencyError", "Recommendation"],
        }

        for issue in self._issues:
            issue_type = type(issue).__name__
            stats["by_type"][issue_type] += 1

            if issue.code:
                stats["by_code"][f"{issue_type}:{issue.code}"] += 1

        return stats

    @property
    def _serialized_issues(self) -> list[dict[str, Any]]:
        """Convert issues to JSON-serializable format."""
        serialized = []
        for idx, issue in enumerate(self._issues):
            issue_type = getattr(issue, "type", type(issue).__name__)
            serialized.append(
                {
                    "id": idx,
                    "type": issue_type,
                    "code": getattr(issue, "code", None) or "",
                    "message": str(getattr(issue, "message", str(issue))),
                    "fix": str(getattr(issue, "fix", ""))
                    if hasattr(issue, "fix") and getattr(issue, "fix", None)
                    else "",
                }
            )
        return serialized

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        issues_json = json.dumps(self._serialized_issues)

        html = f"""
        <style>
            .issues-container {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                max-width: 100%;
                margin: 10px 0;
            }}

            /* Light mode (default) */
            .issues-container {{
                --bg-primary: white;
                --bg-secondary: #f8f9fa;
                --bg-header: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                --text-primary: #212529;
                --text-secondary: #495057;
                --text-muted: #6c757d;
                --border-color: #dee2e6;
                --border-light: #e9ecef;
                --hover-bg: #f8f9fa;
                --stat-bg: rgba(255, 255, 255, 0.2);
                --stat-hover-bg: rgba(255, 255, 255, 0.3);
                --stat-active-bg: rgba(255, 255, 255, 0.4);
                --code-bg: #e9ecef;
                --fix-bg: #e7f5ff;
                --fix-border: #1971c2;
                --fix-text: #1864ab;
                --export-btn-bg: rgba(255, 255, 255, 0.2);
                --export-btn-hover-bg: rgba(255, 255, 255, 0.3);
                --export-btn-border: rgba(255, 255, 255, 0.5);
            }}

            /* Dark mode */
            .issues-container.dark-mode {{
                --bg-primary: #1e1e1e;
                --bg-secondary: #2d2d30;
                --bg-header: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
                --text-primary: #e4e4e7;
                --text-secondary: #a1a1aa;
                --text-muted: #71717a;
                --border-color: #3f3f46;
                --border-light: #27272a;
                --hover-bg: #27272a;
                --stat-bg: rgba(255, 255, 255, 0.1);
                --stat-hover-bg: rgba(255, 255, 255, 0.15);
                --stat-active-bg: rgba(255, 255, 255, 0.2);
                --code-bg: #27272a;
                --fix-bg: #1e293b;
                --fix-border: #3b82f6;
                --fix-text: #60a5fa;
                --export-btn-bg: rgba(255, 255, 255, 0.1);
                --export-btn-hover-bg: rgba(255, 255, 255, 0.2);
                --export-btn-border: rgba(255, 255, 255, 0.3);
            }}

            .issues-header {{
                background: var(--bg-header);
                color: white;
                padding: 20px;
                border-radius: 8px 8px 0 0;
                margin-bottom: 0;
                position: relative;
            }}
            .issues-title {{
                margin: 0 0 10px 0;
                font-size: 24px;
                font-weight: 600;
            }}
            .theme-toggle {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: var(--stat-bg);
                border: 1px solid var(--export-btn-border);
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 600;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .theme-toggle:hover {{
                background: var(--stat-hover-bg);
                border-color: white;
            }}
            .issues-stats {{
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                padding-right: 100px;
            }}
            .stat-item {{
                background: var(--stat-bg);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
                border: 2px solid transparent;
            }}
            .stat-item:hover {{
                background: var(--stat-hover-bg);
                transform: translateY(-2px);
            }}
            .stat-item.active {{
                background: var(--stat-active-bg);
                border-color: white;
            }}
            .stat-number {{
                font-weight: 700;
                font-size: 18px;
            }}
            .issues-controls {{
                background: var(--bg-secondary);
                padding: 15px 20px;
                border-left: 1px solid var(--border-color);
                border-right: 1px solid var(--border-color);
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                align-items: center;
            }}
            .control-group {{
                display: flex;
                align-items: center;
                gap: 8px;
                flex: 1;
            }}
            .search-input {{
                padding: 6px 12px;
                border: 1px solid var(--border-color);
                background: var(--bg-primary);
                color: var(--text-primary);
                border-radius: 6px;
                font-size: 13px;
                width: 100%;
                max-width: 300px;
            }}
            .search-input::placeholder {{
                color: var(--text-muted);
            }}
            .issues-list {{
                background: var(--bg-primary);
                border: 1px solid var(--border-color);
                border-top: none;
                border-radius: 0 0 8px 8px;
                max-height: 600px;
                overflow-y: auto;
            }}
            .issue-item {{
                padding: 16px 20px;
                border-bottom: 1px solid var(--border-light);
                transition: background 0.2s;
            }}
            .issue-item:hover {{
                background: var(--hover-bg);
            }}
            .issue-item:last-child {{
                border-bottom: none;
            }}
            .issue-header {{
                display: flex;
                align-items: start;
                gap: 12px;
                margin-bottom: 8px;
            }}
            .issue-badge {{
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            }}
            .badge-ModelSyntaxError {{
                background: #fee;
                color: #c00;
            }}
            .dark-mode .badge-ModelSyntaxError {{
                background: #7f1d1d;
                color: #fca5a5;
            }}
            .badge-ConsistencyError {{
                background: #fff3cd;
                color: #856404;
            }}
            .dark-mode .badge-ConsistencyError {{
                background: #713f12;
                color: #fcd34d;
            }}
            .badge-Recommendation {{
                background: #d1ecf1;
                color: #0c5460;
            }}
            .dark-mode .badge-Recommendation {{
                background: #164e63;
                color: #67e8f9;
            }}
            .issue-code {{
                padding: 4px 8px;
                background: var(--code-bg);
                border-radius: 4px;
                font-size: 11px;
                font-family: 'Monaco', 'Courier New', monospace;
                color: var(--text-secondary);
            }}
            .issue-message {{
                color: var(--text-primary);
                line-height: 1.5;
                margin-bottom: 8px;
            }}
            .issue-fix {{
                background: var(--fix-bg);
                border-left: 3px solid var(--fix-border);
                padding: 10px 12px;
                margin-top: 8px;
                border-radius: 4px;
                font-size: 13px;
                line-height: 1.5;
            }}
            .issue-fix-label {{
                font-weight: 600;
                color: var(--fix-border);
                margin-bottom: 4px;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .issue-fix-content {{
                color: var(--fix-text);
            }}
            .no-issues {{
                padding: 40px 20px;
                text-align: center;
                color: var(--text-muted);
            }}
            .export-btn {{
                margin-left: auto;
                padding: 6px 14px;
                border: 1px solid var(--export-btn-border);
                background: var(--export-btn-bg);
                color: white;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 600;
                transition: all 0.2s;
            }}
            .export-btn:hover {{
                background: var(--export-btn-hover-bg);
                border-color: white;
            }}
        </style>

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
