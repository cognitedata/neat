HTML_STYLE = """<style>
            .issues-container {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                max-width: 100%;
                margin: 10px 0;
            }

            /* Light mode (default) */
            .issues-container {
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
            }

            /* Dark mode */
            .issues-container.dark-mode {
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
            }

            .issues-header {
                background: var(--bg-header);
                color: white;
                padding: 20px;
                border-radius: 8px 8px 0 0;
                margin-bottom: 0;
                position: relative;
            }
            .issues-title {
                margin: 0 0 10px 0;
                font-size: 24px;
                font-weight: 600;
            }
            .theme-toggle {
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
            }
            .theme-toggle:hover {
                background: var(--stat-hover-bg);
                border-color: white;
            }
            .issues-stats {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                padding-right: 100px;
            }
            .stat-item {
                background: var(--stat-bg);
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
                border: 2px solid transparent;
            }
            .stat-item:hover {
                background: var(--stat-hover-bg);
                transform: translateY(-2px);
            }
            .stat-item.active {
                background: var(--stat-active-bg);
                border-color: white;
            }
            .stat-number {
                font-weight: 700;
                font-size: 18px;
            }
            .issues-controls {
                background: var(--bg-secondary);
                padding: 15px 20px;
                border-left: 1px solid var(--border-color);
                border-right: 1px solid var(--border-color);
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                align-items: center;
            }
            .control-group {
                display: flex;
                align-items: center;
                gap: 8px;
                flex: 1;
            }
            .search-input {
                padding: 6px 12px;
                border: 1px solid var(--border-color);
                background: var(--bg-primary);
                color: var(--text-primary);
                border-radius: 6px;
                font-size: 13px;
                width: 100%;
                max-width: 300px;
            }
            .search-input::placeholder {
                color: var(--text-muted);
            }
            .issues-list {
                background: var(--bg-primary);
                border: 1px solid var(--border-color);
                border-top: none;
                border-radius: 0 0 8px 8px;
                max-height: 600px;
                overflow-y: auto;
            }
            .issue-item {
                padding: 16px 20px;
                border-bottom: 1px solid var(--border-light);
                transition: background 0.2s;
            }
            .issue-item:hover {
                background: var(--hover-bg);
            }
            .issue-item:last-child {
                border-bottom: none;
            }
            .issue-header {
                display: flex;
                align-items: start;
                gap: 12px;
                margin-bottom: 8px;
            }
            .issue-badge {
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            }
            .badge-ModelSyntaxError {
                background: #fee;
                color: #c00;
            }
            .dark-mode .badge-ModelSyntaxError {
                background: #7f1d1d;
                color: #fca5a5;
            }
            .badge-ConsistencyError {
                background: #fff3cd;
                color: #856404;
            }
            .dark-mode .badge-ConsistencyError {
                background: #713f12;
                color: #fcd34d;
            }
            .badge-Recommendation {
                background: #d1ecf1;
                color: #0c5460;
            }
            .dark-mode .badge-Recommendation {
                background: #164e63;
                color: #67e8f9;
            }
            .issue-code {
                padding: 4px 8px;
                background: var(--code-bg);
                border-radius: 4px;
                font-size: 11px;
                font-family: 'Monaco', 'Courier New', monospace;
                color: var(--text-secondary);
            }
            .issue-message {
                color: var(--text-primary);
                line-height: 1.5;
                margin-bottom: 8px;
            }
            .issue-fix {
                background: var(--fix-bg);
                border-left: 3px solid var(--fix-border);
                padding: 10px 12px;
                margin-top: 8px;
                border-radius: 4px;
                font-size: 13px;
                line-height: 1.5;
            }
            .issue-fix-label {
                font-weight: 600;
                color: var(--fix-border);
                margin-bottom: 4px;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .issue-fix-content {
                color: var(--fix-text);
            }
            .no-issues {
                padding: 40px 20px;
                text-align: center;
                color: var(--text-muted);
            }
            .export-btn {
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
            }
            .export-btn:hover {
                background: var(--export-btn-hover-bg);
                border-color: white;
            }
        </style>"""
