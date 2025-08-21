class CookieConsent {
    constructor() {
        this.cookieName = 'cookie_consent';
        this.consentDuration = 365; // days
        this.init();
    }

    init() {
        const consent = this.getConsent();
        if (!consent) {
            this.showBanner();
        } else {
            this.applyConsent(consent);
        }

        this.bindEvents();
    }

    showBanner() {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            banner.classList.add('show');
        }
    }

    hideBanner() {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            banner.classList.remove('show');
        }
    }

    bindEvents() {
        // Accept all cookies
        const acceptBtn = document.getElementById('cookie-accept-all');
        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => {
                this.setConsent({
                    necessary: true,
                    analytics: true,
                    marketing: true,
                    timestamp: Date.now()
                });
                this.hideBanner();
                this.applyConsent(this.getConsent());
                window.location.reload();
            });
        }

        // Reject all cookies
        const rejectBtn = document.getElementById('cookie-reject-all');
        if (rejectBtn) {
            rejectBtn.addEventListener('click', () => {
                this.setConsent({
                    necessary: true,
                    analytics: false,
                    marketing: false,
                    timestamp: Date.now()
                });
                this.hideBanner();
                this.applyConsent(this.getConsent());
                // Reload page to apply changes
                window.location.reload();
            });
        }

        // Settings modal
        const settingsBtn = document.getElementById('cookie-settings');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => {
                this.showSettingsModal();
            });
        }

        // Save settings from modal
        const saveSettingsBtn = document.getElementById('save-cookie-settings');
        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', () => {
                this.saveSettingsFromModal();
            });
        }

        // Enable YouTube videos
        const enableYoutubeBtn = document.querySelectorAll('.enable-youtube');
        enableYoutubeBtn.forEach(btn => {
            btn.addEventListener('click', () => {
                this.showSettingsModal();
            });
        });
    }

    showSettingsModal() {
        const consent = this.getConsent() || {
            necessary: true,
            analytics: false,
            marketing: false
        };

        document.getElementById('cookie-necessary').checked = consent.necessary;
        document.getElementById('cookie-analytics').checked = consent.analytics;
        document.getElementById('cookie-marketing').checked = consent.marketing;

        const modal = new bootstrap.Modal(document.getElementById('cookie-settings-modal'));
        modal.show();
    }

    saveSettingsFromModal() {
        const consent = {
            necessary: document.getElementById('cookie-necessary').checked,
            analytics: document.getElementById('cookie-analytics').checked,
            marketing: document.getElementById('cookie-marketing').checked,
            timestamp: Date.now()
        };

        this.setConsent(consent);
        this.hideBanner();
        this.applyConsent(consent);

        const modal = bootstrap.Modal.getInstance(document.getElementById('cookie-settings-modal'));
        if (modal) {
            modal.hide();
        }

        this.updateContent(consent);
    }

    setConsent(consent) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (this.consentDuration * 24 * 60 * 60 * 1000));
        
        document.cookie = `${this.cookieName}=${JSON.stringify(consent)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
    }

    getConsent() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === this.cookieName) {
                try {
                    return JSON.parse(decodeURIComponent(value));
                } catch (e) {
                    return null;
                }
            }
        }
        return null;
    }

    applyConsent(consent) {
        if (!consent) return;

        // Handle analytics cookies (New Relic)
        if (!consent.analytics) {
            this.blockAnalytics();
        }

        // Handle marketing cookies (YouTube)
        if (!consent.marketing) {
            this.blockMarketing();
        }
    }

    blockAnalytics() {
        // Remove New Relic scripts if present
        const newRelicScripts = document.querySelectorAll('script[src*="newrelic"]');
        newRelicScripts.forEach(script => script.remove());
        
        // Block New Relic if already loaded
        if (window.NREUM) {
            window.NREUM = undefined;
        }
    }

    blockMarketing() {
        // Replace YouTube iframes with placeholder
        const youtubeIframes = document.querySelectorAll('iframe[src*="youtube"]');
        youtubeIframes.forEach(iframe => {
            this.replaceWithPlaceholder(iframe);
        });
    }

    replaceWithPlaceholder(iframe) {
        const placeholder = document.createElement('div');
        placeholder.className = 'youtube-placeholder';
        placeholder.innerHTML = `
            <h5><i class="bi bi-play-circle"></i> YouTube Video</h5>
            <p>This content requires marketing cookies to be enabled.</p>
            <button type="button" class="btn btn-primary enable-youtube">
                Enable YouTube Videos
            </button>
        `;
        
        iframe.parentNode.replaceChild(placeholder, iframe);

        const enableBtn = placeholder.querySelector('.enable-youtube');
        if (enableBtn) {
            enableBtn.addEventListener('click', () => {
                this.showSettingsModal();
            });
        }
    }

    updateContent(consent) {
        // Update YouTube videos if marketing cookies are now enabled
        if (consent.marketing) {
            const placeholders = document.querySelectorAll('.youtube-placeholder');
            placeholders.forEach(placeholder => {
                this.replaceWithVideo(placeholder);
            });
        } else {
            const youtubeIframes = document.querySelectorAll('iframe[src*="youtube"]');
            youtubeIframes.forEach(iframe => {
                this.replaceWithPlaceholder(iframe);
            });
        }
    }

    replaceWithVideo(placeholder) {
        const videoContainer = document.createElement('div');
        videoContainer.className = 'ratio ratio-16x9';
        videoContainer.innerHTML = `
            <iframe src="https://www.youtube-nocookie.com/embed/4dBHXjpFMwA?si=_gVEw6TvZHadBMrN" 
                    title="YouTube video player" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
                    referrerpolicy="strict-origin-when-cross-origin" 
                    allowfullscreen>
            </iframe>
        `;
        
        placeholder.parentNode.replaceChild(videoContainer, placeholder);
    }

    hasConsent(category) {
        const consent = this.getConsent();
        return consent && consent[category] === true;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    window.cookieConsent = new CookieConsent();
});

window.hasCookieConsent = function(category) {
    if (window.cookieConsent) {
        return window.cookieConsent.hasConsent(category);
    }
    return false;
};