        // Cookie Consent Management
(function() {
    const COOKIE_CONSENT_KEY = 'kickline_cookie_consent';
    
    // Get saved consent
    const getCookieConsent = () => {
        const stored = localStorage.getItem(COOKIE_CONSENT_KEY);
        return stored ? JSON.parse(stored) : null;
    };
    
    // Save consent
    const saveCookieConsent = (consent) => {
        localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify(consent));
        window.dispatchEvent(new CustomEvent('cookieConsentChanged', { detail: consent }));
    };
    
    // Show/hide banner
    const showBanner = () => {
        const banner = document.getElementById('cookieBanner');
        if (banner) {
            banner.classList.add('show');
        }
    };
    
    const hideBanner = () => {
        const banner = document.getElementById('cookieBanner');
        if (banner) {
            banner.classList.remove('show');
        }
    };
    
    // Accept all cookies
    window.acceptAllCookies = () => {
        const consent = {
            essential: true,
            analytics: true,
            marketing: true,
            timestamp: new Date().toISOString(),
            choice: 'accept_all'
        };
        saveCookieConsent(consent);
        hideBanner();
    };
    
    // Reject all non-essential cookies
    window.rejectCookies = () => {
        const consent = {
            essential: true,
            analytics: false,
            marketing: false,
            timestamp: new Date().toISOString(),
            choice: 'reject'
        };
        saveCookieConsent(consent);
        hideBanner();
    };
    
    // Open/close modal
    window.openCookieModal = () => {
        const modal = document.getElementById('cookieModalOverlay');
        const consent = getCookieConsent();
        
        // Load saved preferences
        if (consent) {
            document.getElementById('analyticsCookies').checked = consent.analytics || false;
            document.getElementById('marketingCookies').checked = consent.marketing || false;
        }
        
        if (modal) {
            modal.classList.add('show');
        }
    };
    
    window.closeCookieModal = () => {
        const modal = document.getElementById('cookieModalOverlay');
        if (modal) {
            modal.classList.remove('show');
        }
    };
    
    // Save custom preferences
    window.saveCookiePreferences = () => {
        const analytics = document.getElementById('analyticsCookies').checked;
        const marketing = document.getElementById('marketingCookies').checked;
        
        const consent = {
            essential: true,
            analytics: analytics,
            marketing: marketing,
            timestamp: new Date().toISOString(),
            choice: 'custom'
        };
        saveCookieConsent(consent);
        hideBanner();
        closeCookieModal();
    };
    
    // Initialize on page load
    const initCookieConsent = () => {
        const consent = getCookieConsent();
        if (!consent) {
            // Show banner after a short delay
            setTimeout(showBanner, 1000);
        }
    };
    
    // Close modal on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeCookieModal();
        }
    });
    
    // Close modal on overlay click
    document.getElementById('cookieModalOverlay')?.addEventListener('click', (e) => {
        if (e.target.id === 'cookieModalOverlay') {
            closeCookieModal();
        }
    });
    
    // Run initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCookieConsent);
    } else {
        initCookieConsent();
    }
})();

// WhatsApp Float Button with Popup
(function() {
    const whatsappFloat = document.getElementById('whatsappFloat');
    const whatsappPopup = document.getElementById('whatsappPopup');
    const whatsappHelpText = document.getElementById('whatsappHelpText');
    let popupVisible = false;
    let helpTextTimeout;

    // Show help text on page load after 3 seconds
    setTimeout(() => {
        if (!popupVisible) {
            whatsappHelpText.classList.add('show');
            // Hide after 5 seconds
            setTimeout(() => {
                whatsappHelpText.classList.remove('show');
            }, 5000);
        }
    }, 3000);

    // Show help text on hover
    whatsappFloat.addEventListener('mouseenter', () => {
        clearTimeout(helpTextTimeout);
        if (!popupVisible) {
            whatsappHelpText.classList.add('show');
        }
    });

    whatsappFloat.addEventListener('mouseleave', () => {
        helpTextTimeout = setTimeout(() => {
            whatsappHelpText.classList.remove('show');
        }, 500);
    });

    // Toggle popup on click
    whatsappFloat.addEventListener('click', (e) => {
        e.preventDefault();
        popupVisible = !popupVisible;
        if (popupVisible) {
            whatsappPopup.classList.add('active');
            whatsappHelpText.classList.remove('show');
        } else {
            whatsappPopup.classList.remove('active');
        }
    });

    // Close popup when clicking outside
    document.addEventListener('click', (e) => {
        if (!whatsappFloat.contains(e.target) && !whatsappPopup.contains(e.target)) {
            whatsappPopup.classList.remove('active');
            popupVisible = false;
        }
    });
})();

// Scroll Up Button functionality - Fast and responsive
(function() {
    const scrollUp = document.getElementById('scrollUp');

    // Show/hide scroll up button immediately based on scroll position
    const handleScroll = () => {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        if (scrollTop > 300) {
            scrollUp.classList.add('visible');
        } else {
            scrollUp.classList.remove('visible');
        }
    };

    // Fast smooth scroll to top
    const scrollToTop = () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    };

    // Initialize
    if (scrollUp) {
        window.addEventListener('scroll', handleScroll, { passive: true });
        scrollUp.addEventListener('click', scrollToTop);
        
        // Initial check
        handleScroll();
    }
})();

// Theme Switching functionality
(function() {
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    const icon = themeToggle ? themeToggle.querySelector('i') : null;
    
    // Get saved theme from localStorage or default to light
    const getSavedTheme = () => localStorage.getItem('kickline-theme') || 'light';
    
    // Apply theme
    const applyTheme = (theme) => {
        if (theme === 'dark') {
            body.setAttribute('data-theme', 'dark');
            if (icon) {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            }
        } else {
            body.removeAttribute('data-theme');
            if (icon) {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        }
        localStorage.setItem('kickline-theme', theme);
    };
    
    // Toggle theme
    const toggleTheme = () => {
        const currentTheme = body.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    };
    
    // Initialize
    const initTheme = () => {
        const savedTheme = getSavedTheme();
        applyTheme(savedTheme);
        
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }
    };
    
    // Run immediately and also on DOMContentLoaded as fallback
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTheme);
    } else {
        initTheme();
    }
})();