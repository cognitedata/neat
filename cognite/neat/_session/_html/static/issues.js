function initializeStatistics(uniqueId) {
    /**
     * Initialize stat cards with data from attributes and apply colors.
     * Supports light/dark mode with color schema from shared CSS.
     * Uses uniqueId to support multiple instances on the same page.
     */

    function getColor(percentage) {
        if (percentage < 50) return '#10b981';    // green
        if (percentage < 80) return '#f59e0b';    // amber
        return '#ef4444';                         // red
    }

    function renderCards() {
        const container = document.getElementById('statisticsContainer-' + uniqueId);
        if (!container) return;

        const cards = container.querySelectorAll('.stat-card');

        cards.forEach(card => {
            // Skip if already rendered
            if (card.querySelector('.stat-label')) return;

            const current = parseInt(card.dataset.current);
            const limit = parseInt(card.dataset.limit);
            const label = card.dataset.label;
            const percentage = (current / limit * 100) || 0;
            const color = getColor(percentage);

            // Build card HTML
            card.innerHTML = `
                <h3 class="stat-label">${label}</h3>
                <div class="stat-value">
                    <span class="stat-current">${current}</span>
                    <span class="stat-limit">/ ${limit}</span>
                </div>
                <div class="stat-progress-bg">
                    <div class="stat-progress-bar" style="background: ${color}; width: ${Math.min(percentage, 100)}%;"></div>
                </div>
                <div class="stat-usage" style="color: ${color};">${percentage.toFixed(1)}% used</div>
            `;
        });
    }

    function setupThemeToggle() {
        const container = document.getElementById('statisticsContainer-' + uniqueId);
        if (!container) return;

        // Check if theme toggle already exists
        if (container.querySelector('.theme-toggle')) return;

        // Create theme toggle button
        const header = container.querySelector('.statistics-header');
        const themeToggle = document.createElement('button');
        themeToggle.className = 'theme-toggle';
        themeToggle.id = 'themeToggleStats-' + uniqueId;
        themeToggle.innerHTML = '<span id="themeIcon-' + uniqueId + '">🌙</span><span id="themeText-' + uniqueId + '">Dark</span>';

        header.insertBefore(themeToggle, header.firstChild);

        // Load saved theme preference
        const storageKey = 'neat-statistics-theme-' + uniqueId;
        const savedTheme = localStorage.getItem(storageKey) || 'light';
        applyTheme(savedTheme);

        // Toggle theme on button click
        themeToggle.addEventListener('click', () => {
            const isDarkMode = container.classList.contains('dark-mode');
            const newTheme = isDarkMode ? 'light' : 'dark';
            applyTheme(newTheme);
            localStorage.setItem(storageKey, newTheme);
        });

        function applyTheme(theme) {
            const isDark = theme === 'dark';
            const themeIcon = document.querySelector('#themeIcon-' + uniqueId);
            const themeText = document.querySelector('#themeText-' + uniqueId);

            if (isDark) {
                container.classList.add('dark-mode');
                if (themeIcon) themeIcon.textContent = '☀️';
                if (themeText) themeText.textContent = 'Light';
            } else {
                container.classList.remove('dark-mode');
                if (themeIcon) themeIcon.textContent = '🌙';
                if (themeText) themeText.textContent = 'Dark';
            }
        }
    }

    // Render cards and setup theme toggle
    renderCards();
    setupThemeToggle();
}

// Call immediately with uniqueId for Jupyter notebooks
initializeStatistics(uniqueId);

// Also try on DOMContentLoaded for regular HTML pages
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        initializeStatistics(uniqueId);
    });
}