// Cookie banner functionality
document.addEventListener('DOMContentLoaded', function() {
    // Check if user has already accepted cookies
    if (!localStorage.getItem('cookiesAccepted')) {
        // Show the banner
        document.getElementById('cookie-banner').style.display = 'block';
    }

    // Handle accept button click
    document.getElementById('accept-cookies').addEventListener('click', function() {
        // Set cookie acceptance in localStorage
        localStorage.setItem('cookiesAccepted', 'true');
        // Hide the banner
        document.getElementById('cookie-banner').style.display = 'none';
    });

    // Handle decline button click
    document.getElementById('decline-cookies').addEventListener('click', function() {
        // Set cookie acceptance in localStorage
        localStorage.setItem('cookiesAccepted', 'false');
        // Hide the banner
        document.getElementById('cookie-banner').style.display = 'none';
    });
}); 