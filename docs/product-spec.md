# KeptIt Product Specification

## Product vision

KeptIt becomes a person's dependable memory for the internet: one private place to preserve links and the context needed to find them again. It should make saving nearly effortless and retrieval useful even when the user remembers only an idea, source, or approximate date.

## Target users

- People who discover content across several social and publishing platforms
- Researchers, students, developers, creators, and knowledge workers collecting references
- Home cooks, hobbyists, and lifelong learners organizing practical resources
- Anyone whose bookmarks, open tabs, messages, or platform save lists have become unmanageable

## User pain points

- Saved content is fragmented across services and devices.
- Platform-native save lists provide inconsistent organization and search.
- Titles alone rarely match what a user remembers later.
- Links lose meaning when the reason for saving them is not recorded.
- Duplicate saving creates clutter and uncertainty.
- Users may lose access when a post is removed or an account changes, but copying copyrighted media is not an acceptable solution.

## Core product promise

> Never lose anything interesting on the internet again.

The promise means KeptIt reliably remembers where an item came from and why the user cared about it. It does not promise permanent availability of third-party content.

## Main use cases

- Save a Reel, video, post, article, recipe, repository, or general webpage.
- Add a title, personal note, tags, or collections while saving or later.
- Browse a personal library on desktop or mobile.
- Find an item by keyword, platform, tag, collection, or archive status.
- Correct an item's details, archive it without deleting it, or remove it permanently.
- Recognize that an equivalent URL is already saved before creating a duplicate.

## MVP scope

The first working release includes:

- User registration
- User login and logout
- Secure, private user sessions
- Saving an original URL
- Automatic detection for Instagram, YouTube and Shorts, TikTok, Reddit, X, GitHub, and generic webpages
- Optional custom title
- Optional personal note
- Collections
- Tags
- A saved-content library
- Keyword search across supported stored text fields
- Platform filters
- Editing a saved item
- Archiving and restoring a saved item
- Deleting a saved item
- Duplicate-link detection within a user's library
- A responsive, mobile-friendly interface

## Explicit MVP non-goals

- Semantic or natural-language AI search
- Embeddings, pgvector, AI summaries, or automatic AI tags
- Downloading, mirroring, or redistributing video or other copyrighted media
- Browser extensions, native mobile applications, or operating-system share targets
- Social feeds, public profiles, shared libraries, or collaborative collections
- Offline copies of third-party pages
- Comprehensive metadata extraction from every platform
- Imports from every bookmark or platform provider
- Paid plans, recommendations, or analytics dashboards

## Main user journeys

### Register and enter a private library

1. A visitor supplies valid registration details.
2. KeptIt creates an account without exposing whether unrelated accounts exist beyond necessary validation.
3. The user starts an authenticated session and reaches an empty private library.

### Save a link

1. An authenticated user enters a URL and may add a title and note.
2. KeptIt validates and normalizes the URL, detects its platform, and checks the user's library for a duplicate.
3. If unique, KeptIt saves the original URL plus normalized comparison data and user-authored fields.
4. The saved item appears in the library; metadata enrichment may happen later and must not block the save.

### Organize and rediscover

1. The user assigns tags and one or more collections.
2. The user browses or enters keywords and optional platform filters.
3. KeptIt returns only items owned by that user and matching the active criteria.
4. The user opens the original URL on its source platform.

### Maintain the library

1. The user opens an owned item.
2. The user edits its title, note, collections, or tags; archives or restores it; or requests deletion.
3. KeptIt validates the request, verifies ownership, persists it, and communicates success or a safe error.

## Functional requirements

### Accounts and access

- The system shall register users with normalized, unique account identifiers and securely hashed passwords.
- The system shall authenticate valid credentials, log users out, and protect authenticated routes.
- The system shall scope every library, saved-item, collection, and tag operation to the authenticated owner.
- Error responses shall not reveal sensitive account or resource information.

### Saved items

- The system shall accept only supported HTTP or HTTPS URLs that pass validation and network-safety rules.
- The system shall preserve the user-submitted original URL for navigation and store a normalized representation for matching.
- The system shall classify known platforms and fall back to `webpage` for other valid URLs.
- The system shall support optional custom titles and personal notes with documented length limits.
- The system shall allow owners to view, edit, archive, restore, and delete their items.
- Destructive deletion shall require an explicit user action and remove or anonymize dependent data according to the retention policy.

### Organization and discovery

- The system shall let users create, rename, and delete their own collections and tags.
- The system shall allow saved items to belong to multiple collections and have multiple tags.
- The system shall provide paginated library results with stable ordering.
- The system shall support case-insensitive keyword search over custom title, available source title, personal note, and tags.
- The system shall filter results by platform and archive status; collection and tag filtering should be supported where practical.
- The system shall detect normalized duplicate links per user and return the existing item or a clear conflict response.

### Interface

- The interface shall provide clear loading, empty, success, validation, and failure states.
- Core saving, searching, filtering, editing, and archive actions shall work at mobile and desktop viewport sizes.
- Keyboard navigation, visible focus, semantic markup, and meaningful labels shall be included from the start.

## Non-functional requirements

- **Security:** Follow current password, session, CSRF, CORS, authorization, SSRF, and dependency-security practices.
- **Reliability:** Core saves must not depend on third-party metadata availability; database writes must be transactional where appropriate.
- **Performance:** Common authenticated API reads should target a p95 response time below 500 ms under expected portfolio-scale load, excluding third-party calls.
- **Scalability:** Use stateless application services and paginated queries; design indexes around ownership, normalized URLs, platform, archive state, and search.
- **Maintainability:** Keep modules cohesive, interfaces typed, migrations reversible where practical, and dependencies limited.
- **Observability:** Produce structured, privacy-aware logs with request correlation and actionable server errors.
- **Accessibility:** Target WCAG 2.2 AA for production and test critical keyboard and screen-reader flows.
- **Compatibility:** Support current major evergreen browsers and responsive layouts from small mobile screens upward.

## Privacy requirements

- Libraries shall be private by default.
- The application shall collect the minimum account and product data needed.
- Passwords shall never be stored or logged in plaintext.
- Authentication tokens, notes, search queries, and personal metadata shall be excluded from logs.
- Users shall be able to delete their saved items and account data, subject to a documented backup-retention window.
- Production traffic and data shall be encrypted in transit; managed storage encryption shall be enabled at rest.
- Access to operational data shall follow least privilege and be auditable.
- Future summaries, tags, and embeddings shall be treated as private derived user data, with AI-provider use disclosed before release.

## Success criteria

The MVP is successful when:

- A new user can register, authenticate, save a supported or generic URL, and find it again without assistance.
- All required platforms are classified correctly for representative canonical and share URLs.
- Equivalent normalized URLs cannot silently create duplicates within one user's library.
- Users cannot access or mutate another user's resources in automated authorization tests.
- Core workflows pass automated backend and frontend tests and work at defined mobile and desktop breakpoints.
- Metadata-provider failure does not lose or prevent a core URL save.
- No copyrighted video is downloaded or hosted by KeptIt.
- Production readiness checks cover accessibility, security, backups, monitoring, and recovery before public launch.

## Future features

- Safe metadata enrichment, source titles, descriptions, and thumbnails
- YouTube API integration and platform-specific permitted metadata
- AI summaries and automatic tag suggestions
- Embeddings and PostgreSQL pgvector
- Semantic and hybrid keyword/vector search
- Natural-language “ask my library” retrieval grounded in owned items
- Browser extension and mobile share integration
- Progressive Web App capabilities
- Import and export
- Carefully scoped sharing or collaboration, subject to explicit privacy design
