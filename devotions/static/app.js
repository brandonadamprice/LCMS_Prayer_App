/* Shared client-side behavior for every page, extracted from base.html so
   the browser can cache it like styles.css (bump the ?v= query in base.html
   when this file changes). Per-user values come from window.APP_CONFIG,
   which base.html sets inline BEFORE this script loads. Top-level consts and
   function declarations here stay visible to the per-page extra_js /
   body_scripts blocks (scripts share the global scope). */

// Per-user template values (null for logged-out visitors).
const APP_CONFIG = window.APP_CONFIG || {};
const isLoggedIn = APP_CONFIG.isLoggedIn === true;
const userDarkMode = APP_CONFIG.userDarkMode ?? null;
const userFontSizeLevel = APP_CONFIG.userFontSizeLevel ?? null;
const userBackgroundArt = APP_CONFIG.userBackgroundArt ?? null;

// Lightweight toast notifications. Replaces native alert() for
// non-blocking feedback. type: 'info' | 'success' | 'error'.
window.showToast = function (message, type, duration) {
    const container = document.getElementById('toast-container');
    if (!container) { console.log('toast:', message); return; }
    const toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'info');
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    const remove = () => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    };
    const timer = setTimeout(remove, duration || 4000);
    toast.addEventListener('click', () => { clearTimeout(timer); remove(); });
};

// Promise-based confirm dialog. Replaces native confirm().
// Usage: if (await showConfirm("Sure?")) { ... }
window.showConfirm = function (message, opts) {
    opts = opts || {};
    return new Promise((resolve) => {
        const modal = document.getElementById('confirm-modal');
        const msg = document.getElementById('confirm-message');
        const ok = document.getElementById('confirm-ok');
        const cancel = document.getElementById('confirm-cancel');
        if (!modal || !ok || !cancel) { resolve(window.confirm(message)); return; }

        msg.textContent = message;
        ok.textContent = opts.okText || 'Confirm';
        cancel.textContent = opts.cancelText || 'Cancel';
        ok.classList.toggle('button--danger', !!opts.danger);

        function cleanup(result) {
            modal.classList.remove('visible');
            ok.removeEventListener('click', onOk);
            cancel.removeEventListener('click', onCancel);
            modal.removeEventListener('click', onBackdrop);
            document.removeEventListener('keydown', onKey);
            resolve(result);
        }
        const onOk = () => cleanup(true);
        const onCancel = () => cleanup(false);
        const onBackdrop = (e) => { if (e.target === modal) cleanup(false); };
        const onKey = (e) => { if (e.key === 'Escape') cleanup(false); };

        ok.addEventListener('click', onOk);
        cancel.addEventListener('click', onCancel);
        modal.addEventListener('click', onBackdrop);
        document.addEventListener('keydown', onKey);
        modal.classList.add('visible');
        ok.focus();
    });
};

// Global function to set background art
function displayBackgroundArt(data) {
    if (localStorage.getItem('backgroundArt') === 'disabled') {
        return;
    }

    const bg = document.getElementById('art-background');
    const credit = document.getElementById('art-credit');
    const title = document.getElementById('art-title');
    const link = document.getElementById('art-link');

    if (!data || !data.image_url) return;

    const img = new Image();
    img.onload = () => {
        bg.style.backgroundImage = `url('${data.image_url}')`;
        bg.style.opacity = 0.25;
        document.body.classList.add('has-background-art');
    };
    img.src = data.image_url;

    if (title) title.textContent = data.title;
    if (link) link.href = data.link;
    if (credit) credit.style.display = 'block';
}

// Favorites handling
async function toggleFavorite(path, title, callback) {
    if (!isLoggedIn) {
        showToast("Please log in to favorite pages.", "info");
        return;
    }

    try {
        const response = await fetch('/toggle_favorite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path, title: title }),
        });
        const data = await response.json();
        if (data.success) {
            if (callback) callback(data.is_favorite);
        } else {
            console.error('Toggle favorite failed:', data.error);
        }
    } catch (e) {
        console.error('Toggle favorite error:', e);
    }
}

// Devotion path mapping
const PATH_TO_DEVOTION_KEY = {
    '/office/morning': 'morning',
    '/office/midday': 'midday',
    '/office/evening': 'evening',
    '/office/close_of_day': 'close_of_day',
    '/office/night_watch': 'night_watch',
    '/bible_in_a_year': 'bible_in_a_year',
    '/lent_devotion': 'lent'
};

function injectActionButtons() {
    const pageHeader = document.querySelector('.page-header');
    if (!pageHeader) return;

    const currentPath = window.location.pathname;
    // Blocklist similar to before
    if (currentPath === '/' || currentPath === '/login' || currentPath === '/logout' || currentPath === '/settings') return;

    const devotionKey = PATH_TO_DEVOTION_KEY[currentPath];

    // Container for buttons
    const actionsContainer = document.createElement('div');
    actionsContainer.className = 'header-actions';

    if (isLoggedIn) {
        // 1. Favorite Button — icon-only star; fills gold via .active
        let isFav = (APP_CONFIG.favorites || []).some(f => f.path === currentPath);

        const favBtn = document.createElement('button');
        favBtn.className = 'action-pill action-pill--icon btn-favorite';
        favBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';

        function updateFavUI(favState) {
            favBtn.classList.toggle('active', favState);
            favBtn.setAttribute('aria-pressed', favState);
            const label = favState ? 'Remove from favorites' : 'Add to favorites';
            favBtn.setAttribute('aria-label', label);
            favBtn.title = label;
        }
        updateFavUI(isFav);

        // Get title from H1 inside header
        const headerH1 = pageHeader.querySelector('h1');
        let titleToSave = document.title;
        if (headerH1) titleToSave = headerH1.textContent.trim();

        favBtn.onclick = () => {
            toggleFavorite(currentPath, titleToSave, (newFavState) => {
                isFav = newFavState;
                updateFavUI(isFav);
            });
        };
        actionsContainer.appendChild(favBtn);

        // 2. Reminder Button (Only if mapped) — icon-only bell
        if (devotionKey) {
            const remindBtn = document.createElement('button');
            remindBtn.className = 'action-pill action-pill--icon btn-reminder';
            remindBtn.setAttribute('aria-label', 'Set Reminders');
            remindBtn.title = 'Set Reminders';
            remindBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>';
            remindBtn.onclick = () => {
                const now = new Date();
                let minutes = now.getMinutes();

                // Rounding logic: nearest 15
                let roundedMinutes = Math.round(minutes / 15) * 15;

                const d = new Date(now);
                d.setMinutes(roundedMinutes);
                d.setSeconds(0);

                const h = String(d.getHours()).padStart(2, '0');
                const m = String(d.getMinutes()).padStart(2, '0');
                const timeStr = `${h}:${m}`;

                window.location.href = `/reminders?time=${timeStr}&devotion=${devotionKey}`;
            };
            actionsContainer.appendChild(remindBtn);
        }
    }

    // 3. Print Button (everyone) — clean handout for praying in a group.
    // Icon-only to fit beside the other pills on phone-width banners.
    const printBtn = document.createElement('button');
    printBtn.className = 'action-pill action-pill--icon btn-print';
    printBtn.setAttribute('aria-label', 'Print');
    printBtn.title = 'Print';
    printBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>';
    printBtn.onclick = printPage;
    actionsContainer.appendChild(printBtn);

    pageHeader.appendChild(actionsContainer);
}

document.addEventListener('DOMContentLoaded', injectActionButtons);

// Print prep: personal prayers never print unless the user opts in
// here (print CSS hides #personal-prayers-list without this class).
async function printPage() {
    document.body.classList.remove('print-include-personal');
    if (document.querySelector('#personal-prayers-list, .personal-prayers-block')) {
        const include = await showConfirm(
            'Include your personal prayers in the printed copy?',
            { okText: 'Include', cancelText: 'Leave Them Out' }
        );
        if (include) document.body.classList.add('print-include-personal');
    }
    window.print();
}

window.addEventListener('afterprint', () => {
    document.body.classList.remove('print-include-personal');
});

function toggleCard(header) {
    const card = header.parentElement;
    const collapsed = card.classList.toggle("collapsed");
    header.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

// Let keyboard users toggle a collapsible card header (role="button")
// with Enter or Space, like a native button.
function handleCardKeydown(event, header) {
    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
        event.preventDefault();
        toggleCard(header);
    }
}

function togglePersonalPrayers(button) {
    const prayersList = document.getElementById('personal-prayers-list');
    if (prayersList) {
        prayersList.classList.toggle('hidden');
        button.textContent = prayersList.classList.contains('hidden') ? 'Show My Personal Prayers' : 'Hide My Personal Prayers';
    }
}

function togglePicker(button, cardIndex) {
    const picker = document.getElementById("picker-" + cardIndex);
    picker.classList.toggle("visible");
    if (picker.classList.contains("visible")) {
        button.dataset.originalText = button.innerText;
        button.innerText = "Hide List";
    } else {
        button.innerText = button.dataset.originalText || button.innerText;
    }
}

async function selectRef(newRef, cardIndex) {
    const picker = document.getElementById("picker-" + cardIndex);
    picker.classList.remove("visible"); // Hide picker
    const mainButton = picker.previousElementSibling; // The toggle button
    if (mainButton && mainButton.dataset.originalText) {
        mainButton.innerText = mainButton.dataset.originalText;
    }

    const currentRefEl = document.getElementById("ref-" + cardIndex);
    const textEl = document.getElementById("text-" + cardIndex);

    if (currentRefEl.innerText === newRef) {
        return; // Already showing this ref
    }

    currentRefEl.innerText = newRef;
    textEl.innerHTML = "<em>Loading...</em>";
    if (mainButton) mainButton.disabled = true;

    try {
        const response = await fetch("/get_passage_text?ref=" + encodeURIComponent(newRef));
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        textEl.innerHTML = data.text;
    } catch (error) {
        console.error("Error fetching new ref:", error);
        textEl.innerHTML = "<em>Error loading " + newRef + ". Please try again.</em>";
    } finally {
        if (mainButton) mainButton.disabled = false;
    }
}

// Settings and Dark Mode
const menuButton = document.getElementById('menu-button');
const appMenu = document.getElementById('app-menu');

// Control references
const darkModeToggleSidebar = document.getElementById('dark-mode-toggle');
const darkModeToggleSettings = document.getElementById('settings-dark-mode-toggle');
const backgroundArtToggleSettings = document.getElementById('settings-background-art-toggle');

const decreaseFontSidebar = document.getElementById('decrease-font');
const increaseFontSidebar = document.getElementById('increase-font');
const resetFontSidebar = document.getElementById('reset-font');

const decreaseFontSettings = document.getElementById('settings-decrease-font');
const increaseFontSettings = document.getElementById('settings-increase-font');
const resetFontSettings = document.getElementById('settings-reset-font');

// Font size settings
const FONT_SIZES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]; // em
let currentFontSizeIndex = 2; // Default 1.0em

function applyFontSize(index) {
    currentFontSizeIndex = Math.max(0, Math.min(index, FONT_SIZES.length - 1));
    const sizeEm = FONT_SIZES[currentFontSizeIndex];
    document.body.style.fontSize = sizeEm + 'em';

    const isMin = currentFontSizeIndex === 0;
    const isMax = currentFontSizeIndex === FONT_SIZES.length - 1;

    if (decreaseFontSidebar) decreaseFontSidebar.disabled = isMin;
    if (increaseFontSidebar) increaseFontSidebar.disabled = isMax;
    if (decreaseFontSettings) decreaseFontSettings.disabled = isMin;
    if (increaseFontSettings) increaseFontSettings.disabled = isMax;

    const display = document.getElementById('font-size-display');
    if (display) {
        const pct = Math.round(sizeEm * 100);
        display.textContent = `(${pct}%)`;
    }
}

async function saveFontSizePreference(index) {
    localStorage.setItem('fontSizeLevel', index);
    if (isLoggedIn) {
        try {
            await fetch('/save_font_size', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ font_size_level: index }),
            });
        } catch (error) {
            console.error('Failed to save font size preference:', error);
        }
    }
}

function handleIncreaseFont() {
    if (currentFontSizeIndex < FONT_SIZES.length - 1) {
        applyFontSize(currentFontSizeIndex + 1);
        saveFontSizePreference(currentFontSizeIndex);
    }
}
function handleDecreaseFont() {
    if (currentFontSizeIndex > 0) {
        applyFontSize(currentFontSizeIndex - 1);
        saveFontSizePreference(currentFontSizeIndex);
    }
}
function handleResetFont() {
    applyFontSize(2);
    saveFontSizePreference(2);
}

if (increaseFontSidebar) increaseFontSidebar.addEventListener('click', handleIncreaseFont);
if (decreaseFontSidebar) decreaseFontSidebar.addEventListener('click', handleDecreaseFont);
if (resetFontSidebar) resetFontSidebar.addEventListener('click', handleResetFont);

if (increaseFontSettings) increaseFontSettings.addEventListener('click', handleIncreaseFont);
if (decreaseFontSettings) decreaseFontSettings.addEventListener('click', handleDecreaseFont);
if (resetFontSettings) resetFontSettings.addEventListener('click', handleResetFont);

function applyDarkMode(isDark, persist = true) {
    // persist=false is used when following the OS theme: nothing is
    // written, so the site keeps tracking the OS until the user makes an
    // explicit choice (toggle, or a saved account preference).
    if (isDark) {
        document.body.classList.add('dark-mode');
        if (persist) localStorage.setItem('darkMode', 'enabled');
    } else {
        document.body.classList.remove('dark-mode');
        if (persist) localStorage.setItem('darkMode', 'disabled');
    }
    // Sync toggles
    if (darkModeToggleSidebar) darkModeToggleSidebar.checked = isDark;
    if (darkModeToggleSettings) darkModeToggleSettings.checked = isDark;
}

async function saveDarkModePreference(isDark) {
    localStorage.setItem('darkMode', isDark ? 'enabled' : 'disabled');
    if (isLoggedIn) {
        try {
            await fetch('/save_dark_mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dark_mode: isDark }),
            });
        } catch (error) {
            console.error('Failed to save dark mode preference:', error);
        }
    }
}

// Set initial dark mode state: account preference, then an explicit
// local choice, then the OS theme (prefers-color-scheme) as default.
const osDarkQuery = window.matchMedia('(prefers-color-scheme: dark)');
const storedDarkMode = localStorage.getItem('darkMode');
if (isLoggedIn && userDarkMode !== null) {
    applyDarkMode(userDarkMode);
} else if (storedDarkMode !== null) {
    applyDarkMode(storedDarkMode === 'enabled');
} else {
    applyDarkMode(osDarkQuery.matches, false);
    // Keep following OS theme changes until an explicit choice is made.
    osDarkQuery.addEventListener('change', (e) => {
        if (localStorage.getItem('darkMode') === null) {
            applyDarkMode(e.matches, false);
        }
    });
}

// Set initial font size
if (isLoggedIn && userFontSizeLevel !== null) {
    applyFontSize(userFontSizeLevel);
} else {
    const localSize = localStorage.getItem('fontSizeLevel');
    if (localSize !== null) {
        applyFontSize(parseInt(localSize, 10));
    } else {
        applyFontSize(2); // Default
    }
}

// Toggle dark mode listener
function handleDarkModeToggle(e) {
    applyDarkMode(e.target.checked);
    saveDarkModePreference(e.target.checked);
}

if (darkModeToggleSidebar) darkModeToggleSidebar.addEventListener('change', handleDarkModeToggle);
if (darkModeToggleSettings) darkModeToggleSettings.addEventListener('change', handleDarkModeToggle);

// Background Art Logic
function setBackgroundArtPreference(enabled) {
    if (enabled) {
        localStorage.setItem('backgroundArt', 'enabled');
    } else {
        localStorage.setItem('backgroundArt', 'disabled');
        // If disabled, remove visual effects immediately
        document.body.classList.remove('has-background-art');
        const bg = document.getElementById('art-background');
        if (bg) bg.style.backgroundImage = '';
        const credit = document.getElementById('art-credit');
        if (credit) credit.style.display = 'none';
    }
    if (backgroundArtToggleSettings) backgroundArtToggleSettings.checked = enabled;
}

async function saveBackgroundArtPreference(enabled) {
    setBackgroundArtPreference(enabled);
    if (isLoggedIn) {
        try {
            await fetch('/save_background_art', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ background_art: enabled }),
            });
        } catch (error) {
            console.error('Failed to save background art preference:', error);
        }
    }
}

if (backgroundArtToggleSettings) {
    backgroundArtToggleSettings.addEventListener('change', (e) => {
        saveBackgroundArtPreference(e.target.checked);
        // Reload to apply if re-enabling requires fetch, or just let user navigate
        if (e.target.checked) location.reload();
    });
}

// Init Background Art Preference
if (isLoggedIn && userBackgroundArt !== null) {
    setBackgroundArtPreference(userBackgroundArt);
} else {
    // Default to enabled if not set
    if (localStorage.getItem('backgroundArt') === null) {
        localStorage.setItem('backgroundArt', 'enabled');
    }
    setBackgroundArtPreference(localStorage.getItem('backgroundArt') === 'enabled');
}

// Default Background Art Loader
async function loadDefaultArt() {
    try {
        const response = await fetch('/api/art/recent');
        const data = await response.json();
        if (data && data.image_url) {
            displayBackgroundArt(data);
        }
    } catch (e) {
        console.error("Failed to fetch default background art", e);
    }
}

// Load default art if not suppressed by specific page
document.addEventListener('DOMContentLoaded', () => {
    if (!window.suppressDefaultArt) {
        loadDefaultArt();
    }
});

// Toggle app menu
menuButton.addEventListener('click', function (event) {
    const isOpen = appMenu.style.display === 'block';
    appMenu.style.display = isOpen ? 'none' : 'block';
    menuButton.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
    event.stopPropagation();
});

// Close menu if clicking outside
document.addEventListener('click', function (event) {
    if (appMenu.style.display === 'block' && !appMenu.contains(event.target) && event.target !== menuButton) {
        appMenu.style.display = 'none';
        menuButton.setAttribute('aria-expanded', 'false');
    }
});

// Creed Toggle Functions
function showApostlesCreed() {
    const ath = document.getElementById('athanasian-creed');
    const ap = document.getElementById('apostles-creed');
    if (ath && ap) {
        ath.style.display = 'none';
        ap.style.display = 'block';
    }
}
function showAthanasianCreed() {
    const ath = document.getElementById('athanasian-creed');
    const ap = document.getElementById('apostles-creed');
    if (ath && ap) {
        ath.style.display = 'block';
        ap.style.display = 'none';
    }
}

// Milestone Modal Functions
window.triggerMilestoneModal = function (message, streak) {
    document.getElementById('milestone-message').textContent = message;
    document.getElementById('milestone-modal').classList.add('visible');
    if (navigator.vibrate) navigator.vibrate([100, 50, 100]);

    // Store text for sharing
    if (message.includes("Daily Office")) {
        window.milestoneShareText = "I just completed the Daily Office (Morning, Midday, Evening, and Close of Day Prayer) on A Simple Way to Pray! 📖 #Christianity #Prayer";
    } else {
        window.milestoneShareText = `I just reached a ${streak} day prayer streak on A Simple Way to Pray! 🔥 #Christianity #Prayer`;
    }
}

function closeMilestoneModal() {
    document.getElementById('milestone-modal').classList.remove('visible');
}

async function shareMilestone() {
    if (navigator.share) {
        try {
            await navigator.share({
                title: 'Prayer Streak Milestone',
                text: window.milestoneShareText,
                url: window.location.origin
            });
        } catch (err) {
            console.log('Error sharing:', err);
        }
    } else {
        // Fallback to clipboard
        try {
            await navigator.clipboard.writeText(window.milestoneShareText + " " + window.location.origin);
            showToast("Message copied to clipboard!", "success");
        } catch (err) {
            showToast("Could not copy to clipboard. Please share manually.", "error");
        }
    }
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').then(registration => {
            console.log('ServiceWorker registration successful with scope: ', registration.scope);
        }, err => {
            console.log('ServiceWorker registration failed: ', err);
        });
    });
}

// Accordion Menu
var acc = document.getElementsByClassName("menu-accordion");
var i;

for (i = 0; i < acc.length; i++) {
    acc[i].addEventListener("click", function () {
        this.classList.toggle("active");
        var panel = this.nextElementSibling;
        if (panel.style.maxHeight) {
            panel.style.maxHeight = null;
        } else {
            panel.style.maxHeight = panel.scrollHeight + "px";
            setTimeout(() => {
                if (panel.style.maxHeight) {
                    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }, 300);
        }
    });
}

// Global Tooltip Toggle Logic
document.addEventListener('click', function (event) {
    // If clicking ON a tooltip (text or pseudo-element popup)
    if (event.target.classList.contains('scripture-tooltip')) {
        const wasActive = event.target.classList.contains('active');

        // Close ALL tooltips first (so we don't have multiple open)
        const activeTooltips = document.querySelectorAll('.scripture-tooltip.active');
        activeTooltips.forEach(t => {
            t.classList.remove('active');
        });

        // If it wasn't already active, open it.
        // If it WAS active, we just closed it above (toggle off behavior).
        if (!wasActive) {
            event.target.classList.add('active');
        }
    } else {
        // Close all tooltips if clicking outside
        const activeTooltips = document.querySelectorAll('.scripture-tooltip.active');
        activeTooltips.forEach(t => {
            t.classList.remove('active');
        });
    }
});

// ---------------------------------------------------------------------------
// Native app shell (Capacitor) support. Inside the Capacitor WebView (the
// mobile/ project) the shell injects window.Capacitor, and push + Google
// sign-in must go through native plugins because Android WebViews have no
// Push API and Google blocks its OAuth pages in embedded webviews. On the
// regular web isNativeShell is false and this whole section is inert.
window.isNativeShell = !!(window.Capacitor &&
    window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());

if (window.isNativeShell) {
    const { PushNotifications } = window.Capacitor.Plugins;

    // High-importance channel so reminders pop as heads-up banners with
    // sound on Android 8+ (the default channel only lands quietly in the
    // tray). The server tags its FCM messages with this channel_id.
    // Re-creating an existing channel is a no-op, so this runs every launch.
    PushNotifications.createChannel({
        id: 'reminders',
        name: 'Prayer Reminders',
        description: 'Scheduled prayer and devotion reminders',
        importance: 5,
        visibility: 1,
        vibration: true
    }).catch(() => {});

    // Whenever the OS hands us a (possibly rotated) FCM token, persist it
    // server-side and remember it locally so nativePush.disable() can remove
    // it later (the plugin has no "get current token" call).
    PushNotifications.addListener('registration', async (token) => {
        localStorage.setItem('native_fcm_token', token.value);
        try {
            await fetch('/save_fcm_token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: token.value })
            });
        } catch (e) {
            console.warn('Failed to save native FCM token', e);
        }
    });

    // Tap on a system notification (app in background): deep-link to the url
    // the server put in the message's data payload.
    PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
        const data = (action.notification && action.notification.data) || {};
        if (data.url) {
            window.location.href = new URL(data.url, window.location.origin).href;
        }
    });

    // Foreground pushes are not displayed by the OS on Android; surface a
    // toast instead (mirrors the web's onMessage handler in reminders.html).
    PushNotifications.addListener('pushNotificationReceived', (n) => {
        const data = n.data || {};
        const title = n.title || data.title || 'Prayer Reminder';
        const body = n.body || data.body || '';
        showToast(body ? title + ': ' + body : title, 'info', 8000);
    });

    // FCM tokens rotate. If this user already enabled notifications and the
    // OS permission is granted, re-register on every launch (no prompt) so
    // the server always holds a live token.
    if (isLoggedIn &&
        localStorage.getItem('notifications_enabled') === 'true') {
        PushNotifications.checkPermissions().then((status) => {
            if (status.receive === 'granted') PushNotifications.register();
        }).catch(() => {});
    }

    // Push controls used by settings.html's notification toggle in place of
    // the web Notification/getToken flow.
    window.nativePush = {
        async enable() {
            let status = await PushNotifications.checkPermissions();
            if (status.receive === 'prompt' ||
                status.receive === 'prompt-with-rationale') {
                status = await PushNotifications.requestPermissions();
            }
            if (status.receive !== 'granted') {
                showToast('Notifications are disabled for this app. Enable ' +
                    'them under Android Settings > Apps > A Simple Way to ' +
                    'Pray > Notifications.', 'info', 9000);
                return false;
            }
            // Token arrives via the 'registration' listener above, which
            // also saves it to the server.
            await PushNotifications.register();
            return true;
        },
        async disable() {
            const token = localStorage.getItem('native_fcm_token');
            if (token) {
                try {
                    await fetch('/remove_fcm_token', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ token: token })
                    });
                } catch (e) {
                    console.warn('Failed to remove native FCM token', e);
                }
                localStorage.removeItem('native_fcm_token');
            }
            try {
                await PushNotifications.unregister();
            } catch (e) { /* not fatal; token was already removed server-side */ }
        }
    };
}
