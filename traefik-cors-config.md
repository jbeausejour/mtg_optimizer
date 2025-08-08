# Traefik CORS Configuration for MTG Optimizer

## Overview
CORS handling has been moved from the Quart application to Traefik reverse proxy for better performance and centralized management.

## Traefik Configuration

### Method 1: Dynamic Configuration (Recommended)

Add this to your `docker-compose.yml` or Traefik labels:

```yaml
services:
  mtg-backend:
    labels:
      # CORS Middleware
      - "traefik.http.middlewares.cors.headers.accesscontrolallowmethods=GET,POST,PUT,DELETE,OPTIONS"
      - "traefik.http.middlewares.cors.headers.accesscontrolalloworiginlist=http://localhost:3000,https://yourdomain.com"
      - "traefik.http.middlewares.cors.headers.accesscontrolallowheaders=Content-Type,Authorization,X-Requested-With,X-CSRF-Token"
      - "traefik.http.middlewares.cors.headers.accesscontrolallowcredentials=true"
      - "traefik.http.middlewares.cors.headers.accesscontrolmaxage=86400"
      
      # Apply CORS middleware to your backend route
      - "traefik.http.routers.mtg-backend.middlewares=cors@docker"
```

### Method 2: File Configuration

Create `traefik/dynamic/cors.yml`:

```yaml
http:
  middlewares:
    cors:
      headers:
        accessControlAllowMethods:
          - "GET"
          - "POST" 
          - "PUT"
          - "DELETE"
          - "OPTIONS"
        accessControlAllowOriginList:
          - "http://localhost:3000"
          - "https://yourdomain.com"
        accessControlAllowHeaders:
          - "Content-Type"
          - "Authorization"
          - "X-Requested-With"
          - "X-CSRF-Token"
        accessControlAllowCredentials: true
        accessControlMaxAge: 86400

  routers:
    mtg-backend:
      middlewares:
        - "cors"
```

## Environment-Specific Origins

### Development
```yaml
- "traefik.http.middlewares.cors.headers.accesscontrolalloworiginlist=http://localhost:3000,http://127.0.0.1:3000"
```

### Production
```yaml
- "traefik.http.middlewares.cors.headers.accesscontrolalloworiginlist=https://yourdomain.com,https://www.yourdomain.com"
```

### Mixed (Dev + Prod)
```yaml
- "traefik.http.middlewares.cors.headers.accesscontrolalloworiginlist=http://localhost:3000,https://yourdomain.com"
```

## Benefits of Traefik CORS

1. **Performance** - Handled at reverse proxy level before reaching application
2. **Centralization** - One place to manage CORS for all services
3. **Security** - Better control over origins and headers
4. **Flexibility** - Easy environment-specific configuration
5. **Caching** - Preflight requests cached at proxy level

## Application Changes Made

### Removed from `__init__.py`:
- ❌ `from quart_cors import cors` 
- ❌ CORS origins validation
- ❌ `cors()` wrapper configuration

### Added to Security Headers:
- ✅ OPTIONS request handling (204 status)
- ✅ Traefik-compatible preflight responses

## Testing CORS

Test your CORS configuration:

```bash
# Test preflight request
curl -X OPTIONS -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type,Authorization" \
     http://your-api-domain/api/v1/test-cors

# Should return 204 with CORS headers
```

## Troubleshooting

### Common Issues:
1. **403 Forbidden** - Check origin whitelist
2. **Missing Headers** - Verify header configuration  
3. **Credentials Issues** - Ensure `accessControlAllowCredentials: true`
4. **Cache Problems** - Clear browser cache or reduce `maxAge`

### Debug Headers:
Add to Traefik config for debugging:
```yaml
- "traefik.http.middlewares.cors.headers.customrequestheaders.X-Debug-CORS=enabled"
```

## Security Notes

- Never use `*` for origins in production
- Keep allowed headers minimal
- Monitor CORS logs for suspicious requests
- Use HTTPS origins in production
- Consider short `maxAge` for sensitive applications

## Migration Checklist

- [x] Remove `quart-cors` from requirements.txt
- [x] Update Traefik configuration with CORS middleware
- [x] Test all frontend → backend requests
- [x] Verify JWT authentication still works
- [x] Check OPTIONS requests return 204
- [ ] Update documentation
- [ ] Deploy and test in staging