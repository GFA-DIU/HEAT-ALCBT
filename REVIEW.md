# Django Code Review Checklist

## Purpose

This checklist ensures that all code changes in our Django application meet the team's standards for quality, security, maintainability, and performance before being merged into the main branch.

## 1. General Review

| Check | Description |
|-------|-------------|
| PR size | The pull request is small and focused on a single feature or fix. |
| Naming conventions | Class, function, and variable names follow Python and project style guides. |
| Code readability | The code is easy to read, modular, and logically organized. |
| Comments & docstrings | Complex logic is explained using clear comments or docstrings. |
| Dead code | No commented-out or unused code remains. |
| Formatting | Code passes linting (flake8, black, isort). |
| Version control hygiene | Commits are clean, meaningful, and squashed if needed. |

## 2. Django Project Structure

| Check | Description |
|-------|-------------|
| App organization | Code is correctly placed in Django apps following the project's architecture (models, views, serializers, etc.). |
| Separation of concerns | Views, models, and serializers have distinct responsibilities — no business logic in views. |
| Reusability | Common logic is extracted into utils, mixins, or services instead of duplication. |
| Signals and middleware | Used only when necessary; avoid hidden side effects. |

## 3. Settings

| Check | Description |
|-------|-------------|
| Settings | Configurations are environment-based (settings/dev.py, settings/prod.py) and use environment variables. |

## 4. Models & Database

| Check | Description |
|-------|-------------|
| Field choices | Correct field types (e.g., DecimalField for money, DateTimeField for timestamps). |
| Defaults & nullability | Proper use of null, blank, and default. |
| Indexes | Indexes or unique constraints added for frequently queried fields. |
| Meta options | Proper use of ordering, verbose_name, and db_table where relevant. |
| Migrations | New migrations created and committed. No redundant or conflicting migrations. |
| Foreign keys | Use on_delete explicitly (CASCADE, PROTECT, etc.). |
| Data integrity | Validators and constraints ensure consistency. |

## 5. Business Logic / Views

| Check | Description |
|-------|-------------|
| View type | Correct use of APIView, ViewSet, GenericAPIView, or function-based view. |
| Permissions | Access controls correctly set (IsAuthenticated, custom permissions, etc.). |
| Validation | Inputs are validated via serializers or forms, not just in views. |
| Response consistency | API responses follow a consistent schema and status code convention. |
| Error handling | Graceful error handling with meaningful error messages. |
| Pagination & filtering | Implemented for large data responses. |
| Logging | Key actions or errors are logged (avoid printing). |

## 6. Serializers / Forms

| Check | Description |
|-------|-------------|
| Serializer validation | Custom validate_* or validate() methods implemented as needed. |
| Read-only fields | Sensitive or computed fields marked as read_only=True. |
| Nested serializers | Only used when necessary and not overly complex. |
| Form validation | Proper use of clean() and field-specific validation. |

## 7. Security

| Check | Description |
|-------|-------------|
| Secrets | No secrets, API keys, or passwords hardcoded in code or settings. |
| CSRF protection | Proper use of Django's CSRF protection on forms and API views where applicable. |
| Authentication | Authentication logic follows Django's built-in or configured system securely. |
| Authorization | Proper permission classes or decorators are applied. |
| SQL Injection | ORM used instead of raw SQL wherever possible. |
| User data exposure | Sensitive fields (passwords, tokens) not returned in responses. |
| File uploads | Validations on file types and size; use FileField securely. |
| Dependencies | Updated dependencies; no known vulnerabilities (pip-audit, safety). |

## 8. Performance

| Check | Description |
|-------|-------------|
| Query optimization | Use of select_related and prefetch_related to minimize DB hits. |
| Caching | Added where appropriate (Redis, Django cache). |
| Pagination | Implemented for list endpoints. |
| Background tasks | Heavy operations delegated to Celery or async tasks. |
| N+1 issues | Avoided by optimizing ORM queries. |

## 9. Testing

| Check | Description |
|-------|-------------|
| Test coverage | New code includes unit or integration tests. |
| Test isolation | Tests don't depend on other tests or external state. |
| Factories / fixtures | Use Factory Boy or pytest fixtures for consistent data. |
| Assertions | Clear, meaningful assertions verifying expected behavior. |
| CI checks | Tests pass in the pipeline before merge. |

## 10. Dependencies & Environment

| Check | Description |
|-------|-------------|
| Requirements file | Updated with any new dependencies. |
| Pinned versions | Versions locked in requirements.txt or Pipfile.lock. |
| Unused packages | No obsolete dependencies. |
| Environment variables | Loaded securely using django-environ or similar. |

## 11. Documentation

| Check | Description |
|-------|-------------|
| README updated | Instructions for setup, migration, or usage updated. |
| Changelog / release notes | Updated for new features or fixes. |
| API docs | API endpoints updated in Swagger / DRF Docs. |
| Inline comments | Clear explanations for non-obvious logic. |

## 12. Post-Review Actions

| Check | Description |
|-------|-------------|
| All comments addressed | Each reviewer comment is resolved or acknowledged. |
| Tests passed | CI/CD green lights before merging. |
| PR approval | At least one peer reviewer approved. |
| Merge & cleanup | Feature branch merged and deleted after deploy. |

## Tips for Reviewers

- Focus on intent as well as implementation — does the code solve the problem clearly and correctly?
- Ask clarifying questions instead of issuing blunt rejections.
- Keep feedback constructive and educational.
- Balance blocking and non-blocking comments.
- Encourage best practices, not personal style preferences.