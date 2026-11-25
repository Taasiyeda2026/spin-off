# Release verification

The test target was a disposable local stack with GoTrue, PostgREST, Supabase Storage, Supabase Edge Runtime, Kong and PostgreSQL 17. The Dashboard tables and accounts were synthetic. These checks establish application behavior with the actual Supabase services. The production schema and relevant grants were confirmed by an authorized read. Production MFA and a hosted staging release check remain required.

| # | Approved scenario | Evidence |
|---|---|---|
| 1 | Dashboard instructor sign-in | Real GoTrue password session and the Dashboard lookup contract on synthetic accounts. Production lookup and MFA settings pending. |
| 2 | Instructor sees assigned activities | Local integration and SQL role tests, including primary and secondary assignments. |
| 3 | Unique four-digit instructor code | Local integration compared two instructors. SQL verifies format and stability. |
| 4 | Create a group poster | Local browser integration. |
| 5 | Unique six-digit poster code | Local browser integration compared codes from two groups. SQL verifies format. |
| 6 | Correct activity association | Local browser selects the sole activity. SQL rejects forged activity IDs. |
| 7 | Save answers | Local browser saves an answer after reconnect and restores it in a fresh profile. |
| 8 | Save and restore images | Local integration uploads through the real Edge and Storage services and restores the image in a fresh browser profile. |
| 9 | Restore design settings | A live local instructor save restores color, size and glow in the student browser. Background restore also passes the legacy browser test. Repeat with the full design matrix in hosted staging. |
| 10 | Close and reopen | Local integration resumes a saved poster in a clean browser context. Local browser test covers reload and restoration of an existing IndexedDB draft. |
| 11 | Resume from another computer | Local integration uses a separate browser profile with no shared storage. Repeat from a separate device against hosted staging. |
| 12 | Poster appears under its activity | Local integration uses two activities and checks staff visibility. |
| 13 | Instructor edits remotely | Separate instructor and manager edits passed against local Supabase. |
| 14 | Student sees staff edits | Real local integration resumes and sees the manager's saved edit from another profile. |
| 15 | Staff retrieves group code | SQL checks the scoped management result, and the local Chrome demo copies the exact group code. Repeat on target devices. |
| 16 | Student group isolation | Live PostgREST request used one group's session to request another poster and was denied. |
| 17 | Instructor isolation | Local browser and SQL tests. The same checks cover manager isolation; admin sees both teams. |
| 18 | Instructor reassignment | SQL updates live fixture assignments and checks that the previous instructor loses access. Live cascading in the Dashboard workflow remains for hosted staging. |
| 19 | Offline backup and retry | Real local browser goes offline, observes the failure, reconnects and verifies the answer in a fresh profile. |
| 20 | No silent concurrent overwrite | Real browser integration edits in two profiles and verifies the stale write is rejected. Mocked browser flow also verifies recovery of the preserved local copy. |
| 21 | PDF | Local editor creates a single page, with A4 verified by the legacy browser test. Print verification on target devices remains for hosted staging. |
| 22 | Guess limits | Local SQL verifies lockdown before code lookup after the shared failure budget is exhausted, and 90 valid lookups on one instructor code. Real PostgREST integration passes 90 concurrent valid requests spread over two instructor codes. |
| 23 | Existing editing tools | Local compatibility tests cover answers, participant slots, images, background and design. Visual acceptance of the full editor on target devices remains for hosted staging. |
| 24 | Dashboard regressions | 15 Dashboard login regression assertions passed. Dashboard end-to-end login and activity maintenance remain for hosted staging. |
| 25 | Duplicate creates | Two concurrent requests over PostgREST with the same creation parameters return the same poster ID. |

The aggregate production report is in [supabase-production-readonly.sql](supabase-production-readonly.sql). [Setup, hosted staging and rollback](cloud-posters.md) describe the remaining release steps.
