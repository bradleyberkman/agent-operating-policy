# The wave brief

`SKILL.md` is the durable contract: it does not change between batches. A **wave brief** is the variable layer on top of it — the batch, the machine, and who else is writing. Splitting them this way is right, and it has one predictable failure: the durable half is version-controlled and reviewed, and the variable half is hand-written from memory each time.

**Every error that reaches a wave comes in through this layer.** So the brief's job is not to be complete; it is to be *checkable*. State facts in a form the orchestrator can re-derive, and mark the ones that go stale.

## The three fields that go stale, and what to do about them

An orchestrator should treat these as claims to verify in its first minutes, not as premises. Say so in the brief itself, so it does not read as distrust.

**Machine state.** Free disk, free memory, whether a toolchain is mounted, how many worktrees exist, what else is running. All of it is true at writing time and possibly false at dispatch. Write the reading *with its measurement*, so a re-measure is an obvious comparison rather than a judgement call:

> was: `df -h /Users` → 5.1 Gi available, 98% used. **Re-measure before capping anything.**

Never state a derived cap without the number it came from. "Cap at two builders" is unfalsifiable; "cap at two builders because each needs ~1 GB against 5.1 GB free" can be checked, and can turn out to be the wrong constraint entirely.

**File sets.** If they were derived by extracting paths from issue bodies, say so and say to re-derive — an issue may name a file the author did not see, and documents collide across lanes far more often than code does. If they were derived some other way, say which, because that determines what the re-derivation should catch.

**What is already ruled.** "Every decision is made" is only true at writing time. Point at the *live query* that answers it rather than at a list:

> `is:issue is:open label:<decision-label>` — run it; do not trust a hand-written table.

A hand-maintained list of open questions goes stale the moment two branches touch it. If a register in the repository still carries such a table, that is a defect to report, not a source to read.

## Required sections

### 0. Preconditions — verify before spawning anything

The commands to run, with their last known readings, and the explicit instruction to re-measure. Include what is *not* a constraint and why, since an inherited cap is as costly as a missing one.

### 1. Who else is writing right now

- Active evidence-bearing claims, their expiry, and the decisions/contracts they affect. File overlap is risk evidence, not an automatic lock.
- Open pull requests and their branches, with what each one is doing.
- Any shared external resource (design file, database, deployed environment) and who holds it.

### 2. The batch

One row per lane, and for each: its items, intended mutation surfaces, target pull request,
smallest independently useful proof, and current contract epoch/hash. Then, separately:

- **Ownership table.** Name the contract decision owner, permitted writer(s), and integration owner separately. Same-file writers require a declared compatible partition and named reconciliation.
- **Contract invalidation.** A material provisional-contract change publishes a new epoch, names affected lanes, and requires their proof to be revalidated.
- **Actual chokepoints.** Name only work that cannot produce independently useful output before an unavailable result; list adapters, stubs, or false gates that let other work advance.
- **Cross-lane dependencies that the file partition hides.** A lane can be blocked by something no file list shows — an exhaustive `switch` over an enum, a shared constant with two definitions, a generated file. Name any you know of; the orchestrator must still expect to find more.
- **Which lanes must land dormant behind a false gate**, and why.

### 3. Model and effort

The tier and effort per lane, each with one line of reasoning — and the condition that would change it, stated as something to verify rather than assume:

> iOS workers: efficiency-first **only if** a local build is actually reachable. Verify it in §0; if the toolchain volume is unmounted, the same worker cannot see a compile error until a billed CI cycle, which moves it to capability-first — raise the tier and say why.

### 4. What every worker brief must carry

Link `SKILL.md` for the full list. Enumerate here only what *this repository* gets wrong: the exact test target and its likely mis-guess, result lines that are easy to under-read, locks that must wrap specific commands, where design references live, and what the verification bar is when no one can test on device.

### 5. Authorship

Exact identity strings and the trailer, the wrapper that validates them, and the verification command. State that the orchestrator's own merge commits are subject to all of it.

### 6. How you fail, and the check that prevents it

The dispatch ledger, as a table with a row per lane, and the instruction to rebuild it **from the brief rather than from memory**. Include the monitoring command *and* the signal to use when build output lands outside the worktree.

### 7. Refusals

Short, absolute, and specific to the boundaries this batch could plausibly cross.

### 8. Report back

What to report, when, and the closing measurements the next wave depends on.

## What a brief must not do

**Do not route reversible prototype decisions back.** Choose the best-supported provisional default and record it for the walk. Hold only the exact boundary that meets the non-isolatable or high-reversal-cost blocker test.

**Do not plan speculative implementation.** When mutation surfaces are uncertain, run a bounded read-only probe. Dispatch any useful lane the probe can bound; do not serialize all work merely because the final file partition is unknown.

**Do not restate the durable contract.** A restated rule drifts from its original and the worker cannot tell which copy is current. Link it.

**Do not describe a lane's work in a way that presumes it is possible.** "Add the four cases" reads as an instruction; "add the four cases — Lane A found this cannot be done from one file, see its blocker analysis" reads as a scoped problem. The second is what stops a worker from either forcing it or silently dropping it.

## Closing the loop

The brief that ran a wave is evidence about the brief format. When a wave surfaces an error that entered through this layer — a stale premise, a missing file, a partition that hid a dependency — fix it **here**, in the template, not only in the next hand-written brief. Otherwise the same error is re-authored from memory next time, which is the failure this file exists to end.
