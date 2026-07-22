# Final production hardening — Phase D decisions

## D1 — H2 write-lock scope

Deferred as P2. Delivery Run Sheet and OP SHOP Collection generation build their
snapshots from live assignments while holding `BEGIN IMMEDIATE`, then persist the
same snapshot inside that transaction. Moving snapshot construction outside the
lock would introduce a validate/read/write gap and weaken H2 correctness. A
future optimization must first separate mutation commit from response rendering
without moving the authoritative snapshot read outside the transaction.

## D2 — race evidence

Closed with existing evidence. H2 tests use `Barrier` for simultaneous starts
and `Event` hooks at Delivery `_build_trips` and OP SHOP `_build_pickups`. Mutation
threads are released only after generation reaches the intended contention
point. No sleep-based race is used.

## D3 — SQLite ResourceWarning and fixture cleanup

The production connection helper owns and closes application connections. The
remaining Windows artifacts come from tests using native `sqlite3.Connection`
as a transaction context, which commits or rolls back but does not close. The
cancel-order legacy-schema fixture that produced the observed Gate flake now
uses an explicit closing context. The remaining mechanical test-only cleanup is
P2 and does not indicate a production handle leak.

## D4 — API documentation exposure

`/docs`, `/redoc`, and `/openapi.json` are disabled by default. A trusted
diagnostic environment may set `MANUAL_DISPATCH_ENABLE_API_DOCS=true`. This flag
does not change operational API authentication.

## D5 — old authentication generation

No auth epoch was added. The signed operator cookie includes the current stored
password hash, so password reset changes the expected signature and existing
cookies return 401. Logout deletes the cookie and protected API calls remain
default-deny. Existing authentication tests cover these behaviors.

## D6 — Logbook archive and retention

Deferred. Monthly archive policy, retention periods, manifests, restore drills,
and approved deletion procedures require an operational policy. No historical
Logbook file is changed or deleted by this program.
