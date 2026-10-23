# HANDOFF — Friction Log (for Devpost submission, +10% bonus)

Official per-entry format: task attempted → steps taken → expected vs. actual → severity → workaround/fix → actionable suggestion.

---

**Entry 1 — Multi-part voice utterances silently dropped the second claim**

- Task attempted: Let a shopkeeper report two stock problems in one voice note ("freezer delivery never arrived, cups are almost empty").
- Steps taken: Sent the combined utterance to the /api/voice endpoint; checked the audit ledger for both claims.
- Expected vs. actual: Expected two claims (one REFUSED, one EXECUTED). Actual: only the delivery claim was processed — the cups claim vanished silently, with no error and no trace.
- Severity: High — silent data loss in an auditable system is the worst failure mode.
- Workaround/fix: /api/voice now splits utterances on commas into fragments; each fragment becomes its own audited claim with its own verdict (commit abae525).
- Actionable suggestion: For agent frameworks — treat multi-intent utterances as first-class. A single input should never produce a partial silent result; split-then-audit should be the default pattern, not a custom fix.

---

**Entry 2 — Verification trace claimed audio analysis on plain-text input**

- Task attempted: Verify the /api/voice trace log against what the code actually ran, after a text-only test.
- Steps taken: Ran a text input through the endpoint and read the full trace log.
- Expected vs. actual: Expected the trace to describe the real code path. Actual: the trace claimed "ASR_AUDIO_PARSE / acoustic signature & dialect extraction" when the input was plain text — no audio was ever processed.
- Severity: Medium — a technical judge reading the code would catch the bluff and lose trust.
- Workaround/fix: Renamed the trace step to honest "TEXT_PARSE" (commit abae525).
- Actionable suggestion: For agent-demo tooling — adopt a "trace honesty" rule: every trace label must map 1:1 to a real code path; label-vs-code drift should be treated as a bug.

---

**Entry 3 — SQLite database file committed to Git by mistake**

- Task attempted: Push the Handoff repo to GitHub for judges to clone.
- Steps taken: `git add . && git push`, then inspected the repo contents on GitHub.
- Expected vs. actual: Expected a clean source-only repo. Actual: handoff.db (binary, with stale demo claims from local testing) was committed — anyone cloning would see someone else's old data.
- Severity: Low — data hygiene, but embarrassing in front of judges.
- Workaround/fix: `git rm --cached`, added *.db to .gitignore; the app self-seeds on startup so the file was never needed (commits abae525, 05e9631).
- Actionable suggestion: For hackathon repo templates — ship with a .gitignore covering SQLite/binary artifacts by default.

---

**Entry 4 — README demos drifted from code behavior after the multi-claim fix**

- Task attempted: Verify the README's demo scenarios against the live API after the multi-claim split.
- Steps taken: Ran the README's example inputs and compared outputs with the documented verdicts.
- Expected vs. actual: Expected the documented single verdicts. Actual: the same inputs now produced two claims each — docs and code had drifted.
- Severity: Low — docs-only, but judges test READMEs.
- Workaround/fix: Rewrote the demo scenarios with verified single-intent inputs, plus a new scenario showcasing multi-claim behavior (commit d886a0a).
- Actionable suggestion: For solo builders — keep a "README verification" step in the pre-push checklist; the docs are part of the demo surface.

---

**Entry 5 — Latency measurements swung 35x between identical runs**

- Task attempted: Measure /api/voice latency after the multi-claim refactor to confirm no slowdown.
- Steps taken: Timed identical requests across runs — one run measured 70ms, another 2ms, on identical code.
- Expected vs. actual: Expected a stable number. Actual: a 35x swing that looked like the refactor had caused a slowdown.
- Severity: Medium — unverified performance claims in a pitch are dangerous.
- Workaround/fix: Controlled A/B (original vs. refactored, same process, fresh DBs): both measured ~1.5–2ms. Proved it was environment noise, not a regression.
- Actionable suggestion: For anyone benchmarking agent endpoints — always run same-process A/B on fresh state before quoting a number; one-off timings on shared VMs lie.

---

**Entry 6 — Demo video mixed Tanglish inputs with an English voiceover**

- Task attempted: Cut the demo video so the on-screen inputs match the voiceover story.
- Steps taken: Assembled v2 using the original Tanglish-mixed inputs under English narration; watched the full cut.
- Expected vs. actual: Expected a consistent story. Actual: "delivery varala" inputs under an English VO felt inconsistent for US judges.
- Severity: Medium — presentation, but judges form impressions in the first 30 seconds.
- Workaround/fix: Rebuilt the video fully in English, with inputs verified live against the API ("the delivery never arrived" → REFUSED, "cups are empty" → EXECUTED).
- Actionable suggestion: For demo videos — decide the language register before shooting; mixed registers read as unfinished to judges.

---

**Entry 7 — Background music fought the voiceover**

- Task attempted: Score the demo video with ambient background music.
- Steps taken: Added a dark synth pulse under the narration; listened on repeat.
- Expected vs. actual: Expected subtle energy. Actual: the BGM was irritating on repeat listens and fought the voiceover.
- Severity: Low.
- Workaround/fix: Replaced it with a barely-there warm ambient pad at low volume — felt, not heard.
- Actionable suggestion: For demo videos — mix BGM well under the VO and loop the video three times before locking; if it annoys you, it annoys judges.

---

**Entry 8 — Streamlit preset buttons told a different story than the video**

- Task attempted: Align the web app's preset buttons with the video's demo scenarios.
- Steps taken: Clicked each preset and compared inputs and verdicts with the video's REFUSED/EXECUTED story.
- Expected vs. actual: Expected identical inputs. Actual: the presets still carried the old Tanglish-mixed inputs — the app and the video told different stories.
- Severity: Low — demo-consistency issue.
- Workaround/fix: Switched all four presets to English-only inputs and verified each live (REFUSED / REFUSED / EXECUTED / EXECUTED) before pushing (commit ea9bb02).
- Actionable suggestion: For demo builds — treat every demo surface (video, UI presets, README) as one artifact; change one, re-verify all.

---

**Entry 9 — Animated REFUSED stamp covered the verification trace it celebrated**

- Task attempted: Add a theatrical REFUSED stamp animation to the demo video.
- Steps taken: Rendered the stamp landing directly on the verification trace panel.
- Expected vs. actual: Expected the animation to celebrate the audit trail. Actual: the stamp covered the trace timeline it was meant to celebrate.
- Severity: Low.
- Workaround/fix: Changed it to a center-screen slam that holds for 3 seconds, then fades — leaving the trace readable.
- Actionable suggestion: For demo animations — never occlude the evidence you're highlighting; stage effects around it, not on top of it.
