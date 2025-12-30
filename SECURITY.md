# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. **Email**: Send details to the repository maintainer (check GitHub profile)
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release cycle

### Disclosure Policy

- We follow responsible disclosure practices
- Security fixes will be released as soon as possible
- Credit will be given to reporters (unless anonymity is requested)

## Security Best Practices

When using YG Starter in production:

### Environment Variables

- **Never commit `.env` files** to version control
- Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate API keys regularly
- Use separate credentials per environment

### API Keys

- Generate strong `ADMIN_API_KEY` (32+ characters)
- Rotate LLM provider API keys periodically
- Monitor API usage for anomalies

### Database

- Use strong, unique passwords
- Enable SSL/TLS for database connections
- Restrict network access (VPC, security groups)
- Regular backups with encryption

### Docker

- Keep base images updated
- Don't run containers as root (already configured)
- Use Docker secrets for sensitive data
- Scan images for vulnerabilities

### Network

- Enable HTTPS in production
- Configure proper CORS origins
- Use rate limiting (already configured)
- Enable HSTS headers

## Known Security Considerations

### Development Mode

- Admin endpoints are accessible without API key in development
- Debug logging may expose sensitive information
- CORS is more permissive for local development

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `ADMIN_API_KEY`
- [ ] Set explicit `CORS_ORIGINS`
- [ ] Enable HTTPS
- [ ] Review rate limiting configuration
- [ ] Set up log aggregation (no sensitive data in logs)
- [ ] Configure database connection pooling limits
- [ ] Enable Langfuse for LLM monitoring

## Dependencies

We use Dependabot for automated dependency updates. Security patches are prioritized and released promptly.

## Contact

For security concerns, please contact the repository maintainer through GitHub.
