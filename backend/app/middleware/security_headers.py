"""Security headers middleware for enhanced security."""

import os
from quart import request


def add_security_headers(app):
    """Add security headers to all responses."""
    
    @app.after_request
    async def apply_security_headers(response):
        """Apply security headers to all responses."""
        # Prevent XSS attacks
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy - Environment dependent
        if os.environ.get('FLASK_ENV') == 'development':
            # Development: More permissive for React development
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' localhost:* 127.0.0.1:* https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' localhost:* 127.0.0.1:* https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https: localhost:* 127.0.0.1:*; "
                "connect-src 'self' localhost:* 127.0.0.1:* ws://localhost:* wss://localhost:* https://api.scryfall.com; "
                "frame-ancestors 'none'"
            )
        else:
            # Production: Strict CSP
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.scryfall.com; "
                "frame-ancestors 'none'"
            )
        response.headers['Content-Security-Policy'] = csp_policy
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy
        response.headers['Permissions-Policy'] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        
        # Cache control for sensitive pages
        if request.endpoint and any(x in request.endpoint for x in ['login', 'admin', 'settings']):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        # Add Traefik-compatible headers for CORS handling
        # These help Traefik understand the API structure
        if request.method == 'OPTIONS':
            response.status_code = 204
        
        return response
