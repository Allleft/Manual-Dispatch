import json
import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class H1FrontendAuthBoundaryTest(unittest.TestCase):
    def test_server_session_401_and_auth_generation_guard(self):
        auth_actions_uri = (
            PROJECT_ROOT / "frontend" / "js" / "actions" / "auth-actions.js"
        ).as_uri()
        async_guards_uri = (
            PROJECT_ROOT
            / "frontend"
            / "js"
            / "actions"
            / "workspace"
            / "workspace-async-guards.js"
        ).as_uri()
        script = textwrap.dedent(
            f"""
            class MemoryStorage {{
              constructor() {{ this.values = new Map(); }}
              getItem(key) {{ return this.values.get(key) ?? null; }}
              setItem(key, value) {{ this.values.set(key, String(value)); }}
              removeItem(key) {{ this.values.delete(key); }}
            }}
            const storage = new MemoryStorage();
            globalThis.window = {{
              MANUAL_DISPATCH_API_BASE_URL: "",
              location: {{ protocol: "http:", origin: "http://127.0.0.1" }},
              sessionStorage: storage,
            }};
            let resolveFetch;
            globalThis.fetch = () => new Promise((resolve) => {{ resolveFetch = resolve; }});
            const {{ createAuthActions }} = await import({auth_actions_uri!r});
            const makeState = () => ({{
              accountName: "",
              accountId: "",
              isLoggedIn: false,
              authSessionVersion: 0,
              isAuthLoading: false,
            }});

            storage.setItem("manualDispatchAccountName", "Cached Operator");
            storage.setItem("manualDispatchAccountId", "44");
            const deniedState = makeState();
            let deniedRenders = 0;
            const deniedActions = createAuthActions({{
              state: deniedState,
              renderAuthGate() {{}},
              renderBoard() {{ deniedRenders += 1; }},
            }});
            const pendingRestore = deniedActions.restoreAccountSession();
            const cachedStorageAuthorized = deniedState.isLoggedIn;
            resolveFetch({{
              ok: false,
              status: 401,
              statusText: "Unauthorized",
              async json() {{ return {{ detail: "Authentication required" }}; }},
            }});
            await pendingRestore;
            const deniedStorageCleared =
              storage.getItem("manualDispatchAccountName") === null
              && storage.getItem("manualDispatchAccountId") === null;

            globalThis.fetch = async () => ({{
              ok: true,
              status: 200,
              async json() {{ return {{ account_id: 7, account_name: "Server Operator" }}; }},
            }});
            const restoredState = makeState();
            let authenticatedCalls = 0;
            const restoredActions = createAuthActions({{
              state: restoredState,
              renderAuthGate() {{}},
              renderBoard() {{}},
              onAuthenticated() {{ authenticatedCalls += 1; }},
            }});
            await restoredActions.restoreAccountSession();

            const {{ createWorkspaceAsyncGuards }} = await import({async_guards_uri!r});
            const guardState = {{
              isLoggedIn: true,
              authSessionVersion: 10,
              workspaceRoute: "delivery/task-pool",
              activeWorkspace: "delivery",
              dispatchDate: "2026-07-21",
              deliveryTripSummaryDate: "2026-07-21",
              opshopTripSummaryDate: "2026-07-21",
              deliverySavedHistoryDate: "2026-07-21",
              opshopSavedHistoryDate: "2026-07-21",
            }};
            const guardContext = {{ state: guardState, actions: {{}} }};
            const guards = createWorkspaceAsyncGuards(guardContext);
            const oldMutation = guards.captureMutationContext();
            guardState.authSessionVersion = 12;

            console.log(JSON.stringify({{
              cachedStorageAuthorized,
              deniedLoggedIn: deniedState.isLoggedIn,
              deniedStorageCleared,
              deniedRenders,
              restoredLoggedIn: restoredState.isLoggedIn,
              restoredName: restoredState.accountName,
              authenticatedCalls,
              oldMutationCurrent: guards.isDeliveryMutationCurrent(oldMutation),
            }}));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)

        self.assertFalse(result["cachedStorageAuthorized"])
        self.assertFalse(result["deniedLoggedIn"])
        self.assertTrue(result["deniedStorageCleared"])
        self.assertGreater(result["deniedRenders"], 0)
        self.assertTrue(result["restoredLoggedIn"])
        self.assertEqual("Server Operator", result["restoredName"])
        self.assertEqual(1, result["authenticatedCalls"])
        self.assertFalse(result["oldMutationCurrent"])
