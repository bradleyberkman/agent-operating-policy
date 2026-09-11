# Coding and delivery behavior

## Investigate and build

- Read the authoritative code, contract, and live configuration before changing them; adjacency is not authority.
- State the hypothesis, the smallest observation that distinguishes working from broken, and what would falsify it.
- Prove the riskiest seam first. Abstractions earn their place from repeated real callers.
- A sensitive capability lands dormant behind an explicit false gate unless the accepted ticket also authorizes activation. Building and activating remain separately provable changes, but an operator-started ticket session does not need a second operator approval between them.
- Durable deterministic behavior gets proportional durable proof. Use test-first development for regressions, business logic, state transitions, contracts, migrations, authorization, and reusable infrastructure. Each durable proof must name the failure it protects against, identify the non-overlapping owner, and state when the proof should be retired. Raw test counts detect missing files at most; they are not quality evidence. No recurring ceremony attaches to reversible, read-only, deterministic internal work. Exploratory visuals may begin with running evidence and graduate stable invariants into the permanent suite.

## Browser routing

- Choose browser access by use case, not provider. Prefer an API, repository tool, or deterministic fixture when it proves the same behavior without browser state.
- A harness preview pane is the operator-present collaboration surface for local applications: the operator can inspect and mark up the page while the agent responds to that feedback. It is not an agent-controlled browser, is not evidence that the agent controls a browser, and does not inherit the operator's cookies.
- Unattended local verification uses a checked-in managed Playwright test or runner. Reuse the workspace's one application server, allocate its declared port and browser slot, use an ephemeral browser context per scenario, and scope reports and screenshots to the workspace run. A shell may invoke that managed runner; it must not launch a browser binary or an ad hoc Playwright script.
- Playwright MCP is for bounded exploratory navigation and debugging when a durable runner is not yet the right artifact. Stable assertions graduate into the checked-in runner.
- A recurring workflow that genuinely requires login state uses a named persistent service profile, never the operator's personal browser profile. Bind the profile to one service identity, lock it against concurrent use, keep credentials out of prompts and artifacts, and provide an explicit refresh path.
- The operator's personal browser profile, browser-extension agents, and comparable attended computer-control tools are exceptional capabilities. Use them only when the operator explicitly requests an attended task that depends on their existing browser state. Tool availability, a prior session's permission, or a ticket that merely needs web access is not authorization.
- Before browser navigation, prove that the target server or URL answers. Do not retry indefinitely against an unavailable target, leave browser processes behind, or open a visible browser for unattended proof.

## Verification ladder

- Worker lane: the smallest discriminating test plus compile/type/lint proof needed for its change.
- Pull-request head: affected tests and unconditional checks for protected seams.
- Combined or merge-group head: integration/seam proof against the current base and queued changes.
- Deployment candidate: exact-artifact provenance, dry-run/smoke evidence, and rollback or containment.
- Recompute selection after every diff or base change. CI is authoritative only for checks actually run against the current artifact.
- Device-only motion, haptics, audio timing, accessibility, interaction, and final feel belong in a walk; they do not keep routine implementation open.

## Git

Inspect the remote and repository rules first.

- Work on a fresh ephemeral worktree from the fetched default branch. Never start from the session's current branch.
- Use one ticket per branch and the repository's naming/trailer conventions. A combined delivery branch uses one integration/umbrella ticket and references—not closes—constituent tickets whose outcomes outlive that PR.
- Commit explicit paths after inspecting the staged diff; never sweep unrelated user changes into a commit.
- Publish every commit before opening the pull request. Do not push late commits to a branch whose pull request may already have merged.
- Agents author through the configured bot identity. They do not supply the operator's independent review.
- Re-check the base and affected seams before each push. Verify combined behavior after integration, not only each lane.
- A pull request proposes a change. Live activation remains a separately provable action; its authority comes from the accepted ticket or an exact interactive instruction rather than an automatic second approval ceremony.
