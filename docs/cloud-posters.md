# Cloud posters

The public entry stays at `/spin-off/poster.html`. The existing content, artwork, editor and print layout are shared by students and instructors. Access and management controls are available in Hebrew and Arabic. The existing pedagogical text remains as authored.

## Access and persistence

- Instructor sign-in calls the Dashboard's existing username lookup and Supabase password authentication. The Auth user ID must match the lookup, and the poster RPC independently resolves a unique active linked `instructor`, `activities_manager` or `admin`. Staff access tokens stay in memory and are sent in the authorization header. Reopen the instructor entry when the token expires.
- Server-side activity membership uses `public.activities.row_id`, `gefen_number = '57651'`, `activity_season = 'school_2027'`, and a live match of the caller's employee ID against either instructor assignment. Dashboard SELECT policies grant no poster access. A reassignment takes effect on the next request. Previous seasons, other programs and activities without a verifiable row are outside the application scope for every role, including admins. Poster records are retained.
- Activity managers use the same management screen. Both Dashboard mappings must match: `activities.activity_manager` uses the name normalization in `20261025120000_feedback_staff_manager_share_scope.sql`, and an assigned primary or secondary instructor must appear in the manager's active `contacts_instructors.direct_manager` roster as in `20261105085316_manager_board_tracking_gantt_view_access.sql`. The name is resolved from `users.full_name`, `name`, then `username` as in the Dashboard migrations. Ambiguous active manager names fail closed. Roster membership alone cannot grant access to another manager's activity. Every RPC rechecks the scope.
- The instructor code is allocated once and remains stable across the school year. A successful code lookup returns only eligible school and class data and a 20-minute ticket. It does not confer editing or management privileges. One poster per ticket and a unique client request UUID make creation idempotent within that ticket window.
- Poster codes are random and unique, with a ledger preventing reuse after rotation. A valid group code opens an eight-hour session for one poster. Only SHA-256 hashes of the random 256-bit tickets and session credentials are stored. Archived or deleted posters reject student access. Rotation, archive and removal revoke existing student sessions.
- The private schema has RLS and no direct browser access. The public RPC checks every operation. Only an authorized instructor, activity manager or admin can delete or rotate a code, and archive, unarchive and restore are admin actions. Dashboard grants and policies on activities and users are untouched.
- Images are stored by poster UUID and SHA-256 digest in the private `spacetech-posters` bucket. The Edge Function rechecks poster access via the RPC before using the server-only key. It validates content type, size and digest. Previous images are immutable. The RPC checks that every saved image belongs to that poster, and reads through the Edge Function are restricted to images in the current revision. IndexedDB keeps local image data for retry. Supabase JSON stores only references.
- Writes require the revision read by the editor. Identical retried states are idempotent. A genuine revision conflict preserves a browser draft and offers viewing it without writing over the cloud version. The save indicator confirms success after the RPC acknowledges it. Local drafts use the same browser database as the previous editor with separate keys per poster. The previous local draft remains available from the entry screen.
- Successful lookups have separate budgets per instructor (120/minute, 2,400/UTC day) or per group poster (20/minute, 200/UTC day). Valid classroom traffic does not consume a shared failure budget. Each action still has a server-wide budget of 30 failed guesses/minute and 500/UTC day. The database serializes the failure check and charges misses, and stops all lookups before checking any code if that budget is exhausted. This preserves the guessing bound across clients and still means sustained attacks can temporarily block legitimate lookups. Uploads retain per-poster budgets. Retired codes, expired tokens and stale image versions are retained. Agree on school-year retention before adding cleanup.


## Read-only facts to verify on the existing project

The authorized production read confirmed the Dashboard identifiers and lookup RPC, manager predicates and Storage permissions in project `szinlhjuwyiyszdpsdop`. The [read-only aggregate report](supabase-production-readonly.sql) also confirmed the full breakdown for the 40 open activities in `school_2027`:

| Instructor assignment | Manager scope | Count |
|---|---|---:|
| Primary assigned | Matched | 33 |
| No primary or secondary instructor | No matching active manager | 1 |
| No primary or secondary instructor | No assigned instructor on manager's team | 6 |

All 33 assigned activities match the approved rule. The seven unassigned activities do not grant access via a manager or instructor assignment. Admins can see them, and student creation requires an instructor assignment. No Dashboard data correction is required for this release. The seven closed activities from earlier periods are outside the application scope.

Before release, confirm the production MFA requirement and verify the remaining hosting and device checks in managed Staging. Aggregate assignment verification is complete.

## Verification

See the [25-scenario acceptance record](cloud-posters-acceptance.md) for local results and the remaining hosted checks.

### Local

Run from this repository. These tests use synthetic fixtures and make no requests to production.

```sh
python3 -m http.server 8000 --bind 127.0.0.1
# In a second terminal, with Chromium, Playwright for Python and pdfinfo installed:
python3 tests/poster-drafts.browser.py
python3 tests/poster-cloud.browser.py
node --test tests/poster-media.test.mjs
```

Use a fresh disposable PostgreSQL database with `pgcrypto` available and run these files in order with `psql -X -v ON_ERROR_STOP=1`. The first file creates fake Dashboard, Auth and Storage objects and roles. Do not run the fixture or SQL assertions against a real project.

1. `tests/poster-cloud-fixture.sql`
2. `supabase/migrations/20261125130000_cloud_posters.sql`
3. `tests/poster-cloud.acceptance.sql`
4. `tests/poster-manager.acceptance.sql`
5. `tests/poster-season.acceptance.sql`

### Local Supabase integration

Start a fresh disposable Supabase CLI project, with its bundled gateway, Auth, Storage, PostgREST and Edge Runtime. Apply `tests/poster-supabase-fixture.sql` and then the feature migration. Copy the `poster-media` function into that project's `supabase/functions`, serve it with gateway JWT verification disabled and set `POSTER_ALLOWED_ORIGINS=http://127.0.0.1:8123`. Serve this checkout on port 8123. Run:

```sh
POSTER_SUPABASE_PUBLIC_KEY=... POSTER_SUPABASE_SERVICE_KEY=... python3 tests/poster-supabase.browser.py
```

Use only the throwaway keys from the local CLI stack. The script creates synthetic users with the real Auth admin API. It requires an empty fixture and refuses non-loopback hosts. The service key stays entirely in the Python fixture process.

### Hosted Supabase Staging

Use the actual Supabase gateway, Auth, PostgREST, Storage and Edge runtime in staging, with synthetic primary, secondary, unassigned, disabled and admin users and synthetic activities. Include two activity managers with disjoint teams and activities, plus one activity that matches only the owner and one that matches only the roster. Seed the existing username lookup contract and activity assignments. Run the 25 approved acceptance scenarios across two fresh browser profiles. In particular:

- Real username/password sign-in, Auth UUID verification, expiration and role revocation.
- RPC anonymous access with the project publishable key, PostgreSQL grants/RLS, PostgREST error behavior, and isolation even with the existing wide activities policy.
- The complete creation and resume flow, assignment changes, instructor editing from another browser, soft delete, restore, archive, code rotation, session expiry, parallel creation and save conflicts.
- Real Edge CORS and JWT behavior, direct bucket denial, cross-poster media denial, full image upload/download, size/type enforcement, and storage usage during retry.
- Offline edits, reopening from another device, the actual fallback and retry UX, PDF on mobile/desktop, and Dashboard regression for the existing login and activity editing/deletion. Browser tests with mocked network and the PostgreSQL fixture are partial evidence for these scenarios.

### Staging setup and rollback

1. Supply a separate project ref and authorized staging database credentials through the environment's secure configuration. Verify the project ref and database host explicitly before executing any SQL. Apply only the feature migration to the staging database with SQL editor or `psql -X -v ON_ERROR_STOP=1 -f supabase/migrations/20261125130000_cloud_posters.sql`.
2. Deploy the Edge Function from this repository with `supabase functions deploy poster-media --project-ref <staging-ref> --no-verify-jwt`. It performs authorization via the RPC for both staff and student requests. Configure `POSTER_ALLOWED_ORIGINS` on the function with the exact staging browser origin. Supply `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` from the staging Edge runtime's built-in secrets. Keep the service key in the runtime only.
3. Serve the branch from the staging host. In the staging copy of the site, define `window.posterCloudConfig = { url: '<staging project URL>', publishableKey: '<staging publishable key>' }` before loading `poster-access.js`. Check that all requests target staging before running the browser acceptance.
4. Keep the draft PR open until the staged tests have passed and release is explicitly approved. If an approved deployment later needs rollback, revert the static site to the previous revision, disable the feature RPC for anon/authenticated and disable the Edge endpoint. Preserve the private schema, Storage, and IndexedDB for recovery. Do not execute a destructive down migration.
