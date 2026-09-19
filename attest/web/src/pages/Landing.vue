<template>
  <section class="hero">
    <p class="kicker">Academic integrity without surveillance</p>
    <h1>Proof of writing,<br />not a verdict of guilt.</h1>
    <p class="lead">
      Every edit a student makes is hash-chained in their own browser before it leaves. The server only
      accepts events that continue the chain, and a certificate is issued only if the ledger replays to
      exactly the text they submit. Teachers get evidence they can verify — not a score they have to trust.
    </p>
    <div class="cta">
      <RouterLink class="btn primary" :to="{ path: '/signup', query: { role: 'student' } }">I'm a student</RouterLink>
      <RouterLink class="btn" :to="{ path: '/signup', query: { role: 'teacher' } }">I'm a teacher</RouterLink>
      <RouterLink class="btn ghost" to="/login">Log in</RouterLink>
    </div>
  </section>

  <section class="steps">
    <div class="step"><span class="n">1</span><h3>Create a class</h3><p>A teacher makes a class, gets a six-letter code, and posts an assignment.</p></div>
    <div class="step"><span class="n">2</span><h3>Write in the attested editor</h3><p>Students write normally. The ledger syncs live; pastes and rhythm are recorded as provenance, not judgement.</p></div>
    <div class="step"><span class="n">3</span><h3>Submit, then review evidence</h3><p>Submitting issues a Proof-of-Writing certificate. The teacher sees signals, a replay, citation checks and similarity.</p></div>
  </section>

  <section class="cards">
    <div class="card"><h3>Tamper-evident ledger</h3><p>SHA-256 hash chain computed client-side, re-derived server-side, bound to the exact submitted text. Verifiable offline with a 100-line script.</p></div>
    <div class="card"><h3>Process signals</h3><p>Keystroke rhythm, typed-only speed, composition-vs-transcription cadence, revision effort — reported as <em>genuine · review · suspicious</em>, never as accusations.</p></div>
    <div class="card"><h3>Session replay</h3><p>Watch the document come into being, with typed, internal and external spans coloured and pauses and pastes marked on the timeline.</p></div>
    <div class="card"><h3>Citations &amp; similarity</h3><p>DOIs and links resolved against Crossref and the web; in-class overlap found with fingerprinting and shown as highlighted passages.</p></div>
  </section>

  <footer class="foot muted">
    Built at HackMIT 2026 · verify any certificate offline with <code>verifier/attest_verify.py</code> · try the bare engine at <RouterLink to="/attest">/attest</RouterLink>
  </footer>
</template>

<style scoped>
.hero { padding: 56px 0 32px; max-width: 760px; }
.kicker { color: var(--accent); font-weight: 600; font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; margin: 0 0 12px; }
h1 { font-size: 44px; line-height: 1.08; letter-spacing: -0.02em; margin: 0 0 18px; }
.lead { font-size: 17px; line-height: 1.6; color: var(--muted); margin: 0 0 26px; }
.cta { display: flex; flex-wrap: wrap; gap: 10px; }
.btn { padding: 10px 16px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface); color: var(--text); text-decoration: none; font-weight: 600; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn.ghost { background: transparent; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 40px 0; }
.step { border: 1px solid var(--border); border-radius: 10px; padding: 18px; background: var(--surface); }
.n { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: #fff; font-weight: 700; font-size: 13px; }
.step h3, .card h3 { margin: 10px 0 6px; font-size: 16px; }
.step p, .card p { margin: 0; color: var(--muted); font-size: 14px; line-height: 1.55; }
.cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 40px; }
.card { border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; background: var(--surface); }
.foot { font-size: 13px; padding: 20px 0 40px; border-top: 1px solid var(--border); }
code { font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
@media (max-width: 800px) { .steps, .cards { grid-template-columns: 1fr; } h1 { font-size: 34px; } }
</style>
