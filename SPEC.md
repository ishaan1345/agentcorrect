# AgentCorrect Specification - External Evidence

This document maps every AgentCorrect detection to authoritative external sources, proving the tool implements vendor requirements correctly, not opinions.

## Payment Provider Idempotency Requirements

### Stripe
- **Requirement**: `Idempotency-Key` header for POST requests
- **Official Documentation**: https://docs.stripe.com/api/idempotent_requests
- **Quote**: "To perform an idempotent request, provide an additional `Idempotency-Key` header to the request."
- **Implementation**: Header check, case-insensitive per HTTP spec
- **Paths**: `/v1/charges`, `/v1/payment_intents`, `/v1/subscriptions`

### PayPal
- **Requirement**: `PayPal-Request-Id` header for POST requests
- **Official Documentation**: https://developer.paypal.com/docs/api/reference/api-requests/#http-request-headers
- **Quote**: "Use the PayPal-Request-Id header to make POST, PUT, and PATCH requests idempotent."
- **Implementation**: Header check, case-insensitive
- **Paths**: `/v2/checkout/orders`, `/v1/payments/payment`

### Square
- **Requirement**: `idempotency_key` field in request body
- **Official Documentation**: https://developer.squareup.com/docs/build-basics/common-api-patterns/idempotency
- **Quote**: "Square APIs support idempotency for safely retrying requests... include an idempotency_key in the request body."
- **Implementation**: Body field check (not header)
- **Paths**: `/v2/payments`

### Adyen
- **Requirement**: `idempotencyKey` field in request body
- **Official Documentation**: https://docs.adyen.com/development-resources/api-idempotency/
- **Quote**: "To make a request idempotent, add the idempotencyKey object to the request body."
- **Implementation**: Body field check
- **Paths**: `/v71/payments`, `/v68/payments`

### Braintree
- **Requirement**: `Idempotency-Key` header
- **Official Documentation**: https://developer.paypal.com/braintree/docs/guides/transactions/idempotency
- **Quote**: "Include an Idempotency-Key header with a unique value in your request."
- **Implementation**: Header check
- **Paths**: `/merchants/`, `/transactions`

### Checkout.com
- **Requirement**: `Idempotency-Key` header
- **Official Documentation**: https://www.checkout.com/docs/developer-resources/api-reference/idempotency
- **Quote**: "To make an idempotent request, add the Idempotency-Key header."
- **Implementation**: Header check
- **Paths**: `/payments`

### Razorpay
- **Requirement**: `X-Razorpay-Idempotency` header
- **Official Documentation**: https://razorpay.com/docs/api/payments/idempotency/
- **Quote**: "Pass the X-Razorpay-Idempotency header with a unique key."
- **Implementation**: Header check
- **Paths**: `/v1/payments`, `/v1/orders`

### Mollie
- **Requirement**: `Idempotency-Key` header
- **Official Documentation**: https://docs.mollie.com/overview/api-idempotency
- **Quote**: "Include an Idempotency-Key header with a unique value."
- **Implementation**: Header check
- **Paths**: `/v2/payments`

## SQL Injection & Destructive Patterns

### OWASP SQL Injection
- **Source**: https://owasp.org/www-community/attacks/SQL_Injection
- **Tautologies**: "1=1", "''=''", "true", "or 1=1" are classic SQL injection patterns
- **Quote**: "Tautology-based SQL injection... WHERE clause that is always true"
- **Implementation**: AST parsing to detect tautologies structurally, not via regex

### CWE-89: SQL Injection
- **Source**: https://cwe.mitre.org/data/definitions/89.html
- **Quote**: "The software constructs all or part of an SQL command using externally-influenced input"
- **Unbounded DELETE/UPDATE**: Identified as high-risk operations

### PostgreSQL Documentation
- **Source**: https://www.postgresql.org/docs/current/sql-truncate.html
- **TRUNCATE**: "TRUNCATE quickly removes all rows from a set of tables"
- **Risk**: Irreversible data loss in production

## Infrastructure Commands

### Redis
- **FLUSHALL Documentation**: https://redis.io/commands/flushall/
- **Quote**: "Delete all the keys of all the existing databases, not just the currently selected one."
- **Risk Level**: SEV0 - Complete data loss
- **FLUSHDB Documentation**: https://redis.io/commands/flushdb/
- **Quote**: "Delete all the keys of the currently selected DB."

### MongoDB
- **dropDatabase**: https://www.mongodb.com/docs/manual/reference/command/dropDatabase/
- **Quote**: "Removes the current database, deleting all collections and indexes."
- **Risk Level**: SEV0 - Irreversible database deletion

### AWS S3
- **DeleteBucket**: https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeleteBucket.html
- **Quote**: "Deletes the S3 bucket. All objects in the bucket must be deleted before the bucket itself."
- **Risk Level**: SEV0 - Permanent bucket deletion

## HTTP Specification

### RFC 7230 - HTTP/1.1 Message Syntax
- **Source**: https://tools.ietf.org/html/rfc7230#section-3.2
- **Quote**: "Each header field consists of a case-insensitive field name"
- **Implementation**: All header comparisons use lowercase normalization

## Domain Security

### Public Suffix List
- **Source**: https://publicsuffix.org/
- **Purpose**: Prevent subdomain spoofing (e.g., api.stripe.com.evil.com)
- **Implementation**: eTLD+1 extraction to match only legitimate domains

## CI/CD Integration Standards

### Exit Codes
- **POSIX Standard**: https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_08
- **Convention**: 
  - 0 = Success
  - Non-zero = Failure
  - 2 = SEV0 disasters found (blocks CI/CD)
  - 4 = Input error

### GitHub Actions
- **Documentation**: https://docs.github.com/en/actions/creating-actions/setting-exit-codes-for-actions
- **Quote**: "When an action exits with a non-zero status, the workflow run will fail."

## Verification

Every detection in AgentCorrect is:
1. **Vendor-anchored**: Based on official API documentation
2. **Standards-compliant**: Follows HTTP, SQL, and POSIX standards
3. **Security-justified**: Aligns with OWASP, CWE guidelines
4. **CI/CD-ready**: Uses standard exit codes for automation

This is not opinion - it's implementation of documented requirements.