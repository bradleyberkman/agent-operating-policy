---
name: orchestration
description: Contract for running a multi-agent batch in any repository — deciding whether to fan out, measuring the machine before capping concurrency, writing a worker brief that survives without the orchestrator, monitoring where the work actually writes, verifying the merged head rather than the lanes, and integrating under the repository's identity contract. This skill should be used when dispatching parallel implementation agents against a planned batch.
---

# Orchestrate a batch

Use this when a planned batch is large enough that a single agent would serialize it. Judge an orchestration by one question: **did the batch land merged without the orchestrator redoing the work?** An agent whose output must be rewritten cost more than doing the work directly.

This skill is repo-agnostic. A repository that bills CI differently, gates on different checks, or has its own test targets carries those facts in its own skill; read that one too, and prefer it wherever the two disagree.

## Choose the execution topology

Default to one mutation owner per coherent workstream, supported by parallel read-only specialists. Add write-capable lanes only when a short probe shows independently useful, verifiable outputs and the expected wall-clock gain exceeds startup and reconciliation cost.

Evaluate **commutativity**, not file paths alone:

- Same-file changes may proceed when one owner controls the shared contract or the edits express compatible decisions with a cheap, named reconciliation step.
- Different-file changes serialize when they encode incompatible contracts or share an external mutable resource.
- A lane may start before another lane finishes when it can build against an existing contract, adapter, stub, provisional assumption, or false gate and still produce useful proof.
- A dependency blocks dispatch only when the unavailable output is required before the lane can produce independently useful work.

Use a read-only probe before concluding that an uncertain seam is undecomposable. The probe records contract assumptions, candidate file surfaces, runtime-resource needs, independent failure oracles, and the combined-head proof. Keep one mutation owner when the probe finds no stable boundary.

Fanning out agents does not require fanning out pull requests. Combine lanes when one coherent review and combined-head proof are cheaper and clearer. Split delivery when one slow or risky lane would hold unrelated finished work, has a different authority boundary, or is likely to need independent review iterations.

### Derive the file sets yourself, and include the documents

A file set copied from a plan is a claim, not a fact. Re-derive it by extracting every path named in each item's source — issue body, ruling, ticket — and intersecting the results. Two things go wrong when this is skipped:

**Documents collide more often than code does.** Code is naturally partitioned by feature; a shared architecture note, a requirements file, or a runbook is named by every item that touches the concept. Those overlaps are invisible in a code-only disjointness check and produce the same conflict.

Assign one mutation owner per shared contract or document, and say so in every brief. Other lanes may edit the same file only when the owner has declared a compatible partition and owns final reconciliation; otherwise they record the needed change as a finding. A document owned by a *different session* is read-only for the whole batch unless both owners explicitly coordinate the seam.

State ownership as a table that separately names the contract decision owner, permitted writer(s), and integration owner. A worker that has to infer one of those roles will guess in the direction of doing the work.

For a provisional shared contract, stamp the brief with a contract epoch or content hash. The decision owner does not silently change it: publish the new epoch, name affected lanes, and require them to revalidate before carrying earlier proof forward.

## Choose the model and the effort deliberately

A subagent's model defaults to the parent's. Declining to choose is a choice, and on the strongest model it is the most expensive one. Record the tier, the effort, and one line of reasoning in the brief; a choice that cannot be reconstructed cannot be evaluated.

- **Tune effort before switching tiers.** Effort trades intelligence against latency and cost within one model and is the cheaper lever. Raise it for the most demanding agentic work; lower it for mechanical passes.
- **Match the starting strategy to the cost of being wrong.** Start efficiency-first — cheapest capable tier, upgrade where it visibly fails — when an error surfaces immediately. Start capability-first when accuracy outweighs cost, then optimize down.

What separates the two is **whether the worker has a local check**, which is a fact about the machine rather than about the work. Where a compiler or test runner is reachable, a worker's mistakes surface in seconds — the efficiency-first condition. Where they are not, the same worker cannot see a trivial error until a full billed CI cycle later, which moves it to capability-first. **Ask which case the worker is in; verify it, and do not infer it from any document, including this one.**

Anything a script can decide deterministically gets a script, not an agent.

## Measure the machine before you cap concurrency

A concurrency cap inherited from a document is usually wrong, and wrong in both directions: it either wastes capacity or lets a batch thrash. Measure at dispatch time.

**Check every candidate volume, not the obvious one.** Free space on the default disk says nothing about a toolchain volume, an external drive, or a scratch mount. A cap justified by disk pressure evaporates when the work is pointed at a volume with room — and the reverse is also true. Put large, disposable build caches where the space actually is, one distinct path per worker, and require each worker to delete its own as its last act.

**Read the memory number that constrains, not the one that looks alarming.** "Free" and "used" are nearly meaningless under a modern VM system. What hard-subtracts from what a concurrent build can get is **wired** memory, which cannot be paged or compressed, and a large compressor pool indicates existing pressure. A machine with plenty of "used" memory may be fine; one with multi-gigabyte wired is not.

**Name the actual constraint in the report.** "Capped at two" is not a finding. "Capped at two on memory — 8 GB total, 156 MB unused, 3 GB compressor — while disk turned out to be irrelevant because the scratch volume has 265 GB" is one, and it is what lets the next batch fan out correctly.

**Serialize the shared device, do not cap for it.** Where workers contend over one simulator, emulator, database, or port, a blocking lock that queues is better than a concurrency cap that idles. Prefer a lock the kernel releases when its holder dies — an `fcntl` lock on an open descriptor — over a lockfile whose staleness must be guessed from an mtime. Check the lock's timeout before wrapping a long step in it: a queue of slow builds can exhaust a lock sized for fast tests.

## Make the deliverable an artifact, not a message

A worker's final message is a **single point of failure**. It can fail to arrive — silently, and indistinguishably from the worker having died — and when it does, the work is unrecoverable even though it was completed.

So for any deliverable worth more than a sentence, require the worker to **write it to a file** and reply only with the path and a byte count.

**A worker that has a write tool uses it. This is not a preference.** A write tool takes the report as an argument — the text is *data*, and nothing inside it can change what runs. A shell heredoc inverts that: the report is embedded **inside a shell command**, so the report's own text is part of the program. A heredoc ends at the first line matching its delimiter, and everything after that line stops being report content and starts being commands the shell executes.

**The shell form is therefore unsafe for any text the worker did not author itself.** A scraped page, a quoted transcript, a pasted excerpt, a user's own words copied into a summary — any of these can contain the delimiter, and what follows it then runs. A report that quotes this very section contains a delimiter by construction. If the report will carry material from outside the worker, a write tool is **required**, and a worker without one is the wrong worker for the job.

Use the shell form only when the worker has no write tool and the report is entirely its own prose, and generate the delimiter freshly per dispatch. Either way the report lands at a scratch path and is renamed into place only once the write is *proven* complete:

```sh
mkdir -p "$OUT"
FINAL="$OUT/<subsystem>.md"          # $OUT is unique per dispatch
cat > "$FINAL.partial" <<'PICK_A_FRESH_DELIMITER'
…the full report…
=== END OF REPORT ===
PICK_A_FRESH_DELIMITER
tail -n1 "$FINAL.partial" | grep -qx '=== END OF REPORT ===' \
  && mv "$FINAL.partial" "$FINAL" \
  || echo TRUNCATED               # rename is atomic within one filesystem
wc -c "$FINAL"
```

Three details carry the weight, and all three exist to stop the monitoring table below from reading a lie:

**Rename, never write in place.** `cat > file` creates the file *before* any content lands, so a worker that dies mid-report leaves a file that exists, is non-empty, and is truncated at an arbitrary byte — which the monitoring table reads as **delivered**. Because `mv` within one filesystem is atomic, presence at the final path can only mean the write was checked.

**Gate the rename on the report's own last line.** An unconditional `mv` promotes a truncation to the final path, converting a failure the `.partial` row catches into one nothing catches. This is a **correctness** check on the file, not a safety boundary on the write — it cannot undo whatever the shell already ran.

**Make `$OUT` unique per dispatch.** Stamp it with the run, so a re-dispatch cannot read the previous attempt's file and call it fresh. A stale complete artifact is the hardest failure of the three: indistinguishable from success, and wrong in a way that survives review.

Quoting the delimiter matters too: unquoted, the shell expands backticks and `$` inside the report, silently corrupting any document containing code.

**Check the agent type can write before choosing it.** A read-only search agent has no write tool, so its only delivery path is the return message. Match the agent's tools to how the result gets out, not only to how it gets gathered.

## Write a brief that survives without the orchestrator

A worker cannot ask a clarifying question cheaply, and a worker that guesses produces work that must be audited. The brief must be complete on first read. `references/wave-brief.md` is the template and the list of fields that go stale.

Design focused workers: one worker, one job. A grab-bag brief produces grab-bag output. Grant only the tools the job needs.

Where an authority already exists, **link it rather than restating it**. A restated rule drifts from its original, and the worker cannot tell which copy is current.

Every brief carries:

1. **Model and effort**, with the reason.
2. **Deliverable and definition of done** — and whether the worker owns the review loop or hands back at pull-request open.
3. **The worktree precondition**, verbatim.
4. **Skills to load**, stated as newer than the worker's training.
5. **The ownership table** — contract decision owner, permitted writers, integration owner, what other live workers own, and what is read-only for everyone.
6. **The item list**, each item carrying its files, seam, authority, smallest proof, and assumptions.
7. **Scope discipline** — build at the scope intended; do not widen, quietly narrow, or transform a ruling. A ruling that looks wrong gets one sentence in the report and is then implemented as specified.
8. **What the worker cannot prove**, and the report format.

### The worktree precondition

Give this to every worker verbatim. It runs before reading or diffing anything.

**Resolve the trunk rather than assuming it.** `origin/main` is a convention, not a fact — a repository may use a different default branch or a differently named remote, and hardcoding it turns the one step that must never fail into the first thing that does. Derive it once and use the variable everywhere:

```sh
REMOTE=${REMOTE:-origin}
TRUNK=$(git symbolic-ref --quiet --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null | sed "s#^$REMOTE/##") \
  || TRUNK=$(git remote show "$REMOTE" | sed -n 's/.*HEAD branch: //p')
: "${TRUNK:?cannot resolve the default branch — halt rather than guess}"

WT=<a fresh path, one worktree per worker, never shared>
cd <the repository root>
git fetch "$REMOTE"
git worktree add "$WT" "$REMOTE/$TRUNK"
cd "$WT"
git rev-list --count "HEAD..$REMOTE/$TRUNK"   # MUST print 0 — halt otherwise
git rev-parse --short HEAD                     # print and record
git switch -c <type>/<ticket-id>-<slug>
```

If `refs/remotes/$REMOTE/HEAD` is unset — common on a fresh clone — `git remote set-head "$REMOTE" -a` populates it once. Halting on an unresolved trunk is deliberate: a worker that guesses wrong branches from the wrong base and everything it then verifies is verified against the wrong tree.

Where a repository's own skill states its trunk and remote, that is the more specific authority; use it and skip the resolution.

All work happens in that worktree, never a session's default checkout. When observed behavior appears to contradict the code, suspect staleness first and re-run the assert.

**A worker that only needs to *read* canonical material gets a ref, not a path:**

```sh
git -C <repo> fetch -q "$REMOTE"
git -C <repo> show "$REMOTE/$TRUNK:<path>"      # see the worktree precondition for $REMOTE/$TRUNK
```

Handing out a checkout path couples the worker to whatever state that tree holds, and the failure is silent: the file reads successfully and is simply old. A ref either resolves to current content or errors.

**Put the path in the brief, never in a correction.** A worker that has already started reading is expensive to redirect and may never re-ground. Worse, **a worker's own subagents inherit the original brief**, so one redirect leaves a second tier still reading the wrong tree. Require the worker to state the same premise to anything it spawns.

**A delivered correction is not a followed one.** A send that returns success proves delivery, not compliance. When a redirect matters, require the worker to answer *which path it is reading and what fraction of its findings predate the correction* — and treat any answer short of that as unverified.

Instruct workers to address files by absolute path, or to `cd "$WT" && …` within a single shell call, and **not** to invoke session or environment management tools the brief never named. A blocked call is invisible to the orchestrator and burns wall-clock while resembling progress.

### One writer per shared external resource

A git worktree isolates the repository. It isolates nothing else. Any resource that lives outside version control and is mutated in place — a design file, a live database, a deployed environment — has no branch, no merge, and no conflict marker. Two writers there do not conflict loudly; they interleave and produce a result neither intended, which the second writer reports as success because its own calls all returned cleanly.

**Exactly one writing agent per external resource at a time.** Read-only agents may run concurrently with the writer and with each other. State in every brief which resource the worker may write and that it is the sole writer.

**Idle is not finished.** An agent that has completed its task and remains available is still a writer as far as the resource is concerned — it can be resumed, and it may act on a stale plan. **Stand a worker down explicitly** when its task closes, naming the files and resources it must no longer touch, rather than relying on it having nothing left to do.

**Serialize dispatch, not just execution.** The window opens when a worker is *spawned*, not when its first write lands.

**Split the work at the read/write seam — that is where the savings are.** Mutating a shared resource cannot parallelize; *deciding what to change* parallelizes perfectly, because it is reads with no shared mutable state. Fan out cheap-model agents to produce a pre-resolved specification, then execute serially against it. Brief those research agents to **never call the write tool at all**, and say why: "if you think you need to change it, that is a finding to record, not an action to take."

### State the verification bar, because workers overclaim

Name the substitutes in the brief, and require **`NOT VERIFIED` explicitly** for anything the worker did not observe. A belief phrased as a result is indistinguishable from a fact until it reaches the real system.

**Check whether the worker can actually compile or run before deciding what proof to demand.** Where a local build is reachable, it is the strongest cheap proof and should be required rather than accepted as optional. Where it is not, the worker must instead re-read its own diff as the compiler would.

**Require the pull-request number the moment the pull request opens, not once its checks are green.** A worker that pushes and then sits on its own CI produces the same silence as a worker that died. Reporting on open costs the worker nothing and lets the orchestrator watch the checks — which it can do for every batch at once, and a worker cannot do for even one.

## Never let the orchestrator become the stuck one

The orchestrator's characteristic failure is harder to see than a stuck worker's, because nothing errors: it picks one batch, waits for that batch's CI, and stops dispatching. From the outside the sweep looks alive while batches with no dependency on any of it sit untouched.

**Waiting is not work.** A check that is running needs nothing from you.

**1. Never idle while an independent batch is undispatched.** Only when every batch is dispatched, blocked with a named reason, or explicitly out of scope may the orchestrator wait — and then it waits on all of them at once.

**2. Run the dispatch ledger before every wait.** Restate the full batch list and mark each one:

| Batch | State | If blocked, on what |
| --- | --- | --- |
| L-1 | dispatched | — |
| L-3 | **not dispatched** | *nothing* ← dispatch it now |

A batch whose blocker is "nothing" is a dropped instruction, not a wait. **Reconstruct that list from the brief, never from memory of what you dispatched** — the failure it catches is an instruction that was read and then never acted on, and memory of the sweep has already lost it.

**A worker inherits this.** A worker that finishes its push and then waits on its own CI is doing the same thing at a smaller scale.

## Monitor where the work actually writes

Check when a worker's files were last written, not whether they exist. Existence is a fact about the past.

```sh
find "$WT" -newermt '-10 minutes' -type f -not -path '*/.git/*' | head
```

**This recipe goes blind the moment build output lives outside the worktree** — which is exactly what happens when build caches are pointed at a different volume for space. A worker in a long compile writes nothing under `$WT` and reads as dead. Watch the place the work actually lands:

```sh
du -sh "$DERIVED_DATA_PATH"      # growing = alive
```

Choose the signal from where the worker was told to write, not from habit. A worker whose phase is *reading* writes nothing anywhere — silence during a plausible reading window is not evidence of anything.

**Silence has two causes, and they need opposite responses.** A quiet worker is either stuck, or finished and unable to hand its result back. Killing the first is correct; killing the second pays for the sweep twice.

| Signal | Reading |
| --- | --- |
| No artifact, no writes anywhere in a window that should contain them | **Blocked.** Ask once; then kill and re-dispatch with a changed brief. |
| Artifact at the **final** path in **this dispatch's** `$OUT`, no report reached the orchestrator | **Delivered, unreachable.** Read the artifact. Do not re-dispatch. |
| Only a `.partial` file present | **Died mid-write.** Treat as blocked; the content is truncated at an arbitrary byte. |
| Worker reports idle having sent nothing | **Unknown.** Ask it to write to a file before concluding anything. |

Re-dispatch only after the artifact is confirmed absent.

## Verify the merged head, not the lanes

**Per-lane green does not compose.** Each worker branches from the same base and tests against it, so a change that is correct in isolation can be wrong beside another lane's — and every lane reports success. The merge is a state no worker ever tested.

Two failure shapes recur:

- **A shared constant with two definitions.** One lane changes a value; another lane changes a *reference* to it. Each branch resolves to the old value and passes. Only merged does the new value appear — in tests neither lane owned.
- **A change whose counterpart is out of every lane's file set.** A lane correctly declines to edit a file it does not own and flags it. If nothing picks the flag up, the merged result is half a change.

So run the batch's real gate **on the integration head**, and compare **test identities rather than totals**. Raw counts can detect a missing file, but they are not quality evidence: additions can compensate for silently removed or overwritten proofs while the total stays unchanged. Capture the test names before and after, diff them, and reconcile every addition or removal to the lane and failure contract that owns it.

**Read every lane's `BLOCKED ON` before integrating.** A worker naming a file outside its set is describing a change that will otherwise ship half-done. That is the orchestrator's to complete or to state as unlanded — not to let through silently.

**When a change crosses a trust boundary, verify the receiver.** A renamed wire value, a new field, a changed enum encoding: check what the *deployed* counterpart accepts, in its own source, not in the client's tests. A client that leads its server ships a break that every local suite passes.

## Falsify what you verify

A test that has never failed has not been shown to work. Before trusting a new check, **break the thing it targets and confirm it goes red** — then restore and re-run clean.

**Falsify against the exact seam.** A defended path can silently repair the defect and the test passes anyway: if a merge, a fallback, or a default restores the value the test asserts, the test proves nothing about the code it was written for. Pick the seam with no defence behind it, and confirm that *specifically* the intended test fails while its neighbours stay green.

The same discipline applies to claims. **A claim you carry from a worker's report into a pull-request body becomes your evidence, and inherits your credibility.** Verifying one claim in a report and passing the rest through unchecked is worse than checking none, because it produces the feeling of diligence without its substance. Verify every claim you restate, or attribute it and say it is unverified.

## Integrate without breaking authorship

Follow the repository's recorded identity and trailer contract for interactive commits and pull-request publication. Unattended automation retains its named, scoped service identity. Include the tool's co-author trailer when the contract requires it. Commit attribution and publication do not constitute the operator's independent review or approval.

**The integrator's own merge commits are commits too.** Apply the same recorded identity and trailer contract. Set the identity in the environment before the first merge rather than per commit.

**Consolidating worker branches rewrites the committer.** Cherry-picking preserves the author but stamps the consolidating identity as committer. Merging worker branches instead avoids the rewrite entirely, at the cost of a messier history; prefer it for large batches.

Verify before opening the pull request:

```sh
git log "$REMOTE/$TRUNK..HEAD" --format='%h %an <%ae> | %cn <%ce> | %(trailers:key=<TrailerKey>,valueonly)'
```

Every line must match the recorded author and committer identities and carry the required trailers.

**A base that moved invalidates assumptions, not automatically every test.** Re-fetch before integrating, inspect the changed contract/seam, and recompute the affected proof. Re-run the combined gate when compiled behavior, an integration seam, or the composition changed; retain narrow evidence only when the impact analysis shows its oracle and inputs are unchanged.

## Converge in one review round

Every pushed head commit buys a fresh paid reviewer call, and often a full CI run. Four review rounds cost four times one.

Audit the batch's own diff before pushing, for the contradictions a reviewer reliably finds:

- comments describing behavior the diff removed
- documentation referencing a moved or deleted file
- identifiers reused across two workers' items
- **claims in the pull-request body that the diff does not support**
- availability gaps against the deployment floor
- ticket references that do not match the work

Then fix every finding in a single push. **When scope changes, every artifact describing it changes in the same push** — body, file headers, and comments included.

**A reviewer finding is a hypothesis, not a verdict.** Check it against the source before acting. Some are correct and expensive to miss; some describe a state the system cannot reach. Fix the first kind, and refute the second **with evidence, in a comment, without pushing a code change** — a push spends a billed round to satisfy a bot on something you can settle with a citation. A product-intent disagreement stops only when it meets the universal non-isolatable or high-reversal-cost blocker test; otherwise choose the strongest provisional direction, isolate it, and route acceptance to the next walk.

## Refusals

- Never approve a pull request, admin-merge, or push to a protected branch. A session's CLI usually carries the human's identity, so an approval through it spoofs their review.
- Never ask for, wait on, or nudge a merge.
- Never spawn workers with permission checks disabled without explicit authorization.
- Never let a worker open a draft pull request, and never let one report success it did not observe. A recoverable pushed checkpoint branch without a PR is allowed when another lane or the integrator needs its commit; it grants no delivery or CI claim.
- Never re-dispatch a failing brief unchanged. Repeated failure is a framing problem: the brief is wrong, not the agent.
- Never re-dispatch on silence alone. Confirm the artifact is absent first.
- Never treat a worker's self-report as verification. Spot-check its paths and line numbers before any of them reaches a ruling, a brief, or a pull-request body.
- Never wait on a check while a batch with ready inputs is undispatched.
- Never conclude the sweep, or report status, without restating the batch list **from the brief**.
