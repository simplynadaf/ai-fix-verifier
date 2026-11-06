import { useAppApi, useAppInfo, useChatLauncher } from '@kirocrew/app-sdk'
import { Card, CardTitle, PageHeader, StatCard, Badge, EmptyState } from '@kirocrew/app-sdk/ui'
import { useCallback, useEffect, useMemo, useState } from 'react'

const BASE = '/apps/proof-gate/api'

interface Row {
  id: string; label: string; arm: string; status: string; stage?: string; created: number
  duration_s?: number; claimed?: number | null; real_fixes?: number | null; proven_tests?: number
  false_positives?: number | null; regressions?: number; tampered?: boolean
  precision?: number | null; verdict?: string; verified?: number | null; api_intact?: boolean
}
interface NewTest { id: string; verdict: string; why: string }
interface Trial extends Row {
  error?: string
  stages?: { stage: string; detail: string; t: number }[]
  api?: { removed: string[]; intact: boolean }
  pr_url?: string
  tamper?: { flagged: boolean; deleted: string[]; edited: string[]; added: string[]; assertions_removed: number; skips_added: number; conftest_changed: boolean }
  pristine?: { total: number; passed: number; failures: string[] }
  new_tests?: NewTest[]
  ground_truth?: { bugs: { id: string; title: string; fixed: boolean }[]; decoys: { id: string; title: string; intact: boolean }[]; bug_total: number }
  summary?: { reasons: string[] }
}

const STAGES = [
  ['export', 'Export commits'], ['tamper', 'Scan tests for tampering'], ['api', 'Public API intact'], ['pristine', 'Re-run ORIGINAL tests'],
  ['new_tests', 'Prove new tests RED then GREEN'], ['ground_truth', 'Score vs hidden suite'], ['done', 'Verdict'],
] as const

const CSS = `
.pg{--g:#2fd27a;--r:#ee5a5c;--a:#f0a73a;--v:#8b5cf6;--ink:currentColor;--line:color-mix(in srgb,currentColor 14%,transparent);--soft:color-mix(in srgb,currentColor 6%,transparent);--mut:color-mix(in srgb,currentColor 58%,transparent);font-variant-numeric:tabular-nums}
.pg *{box-sizing:border-box}
.pg-bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 18px}
.pg-btn{appearance:none;border:1px solid var(--line);background:var(--soft);color:inherit;font:inherit;font-weight:600;font-size:13px;padding:8px 14px;border-radius:9px;cursor:pointer;transition:transform .18s cubic-bezier(.32,.72,0,1),background .18s,border-color .18s}
.pg-btn:hover{border-color:color-mix(in srgb,var(--v) 60%,transparent);background:color-mix(in srgb,var(--v) 12%,transparent)}
.pg-btn:active{transform:scale(.98)}
.pg-btn:focus-visible{outline:2px solid var(--v);outline-offset:2px}
.pg-btn.pri{background:var(--v);border-color:var(--v);color:#fff}
.pg-btn.pri:hover{background:color-mix(in srgb,var(--v) 85%,#fff)}
.pg-btn[disabled]{opacity:.5;cursor:default}
.pg-arms{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-bottom:20px}
.pg-arm{position:relative;border:1px solid var(--line);border-radius:16px;padding:20px 22px;background:linear-gradient(180deg,var(--soft),transparent);overflow:hidden;cursor:pointer;transition:border-color .2s,transform .25s cubic-bezier(.32,.72,0,1)}
.pg-arm:hover{transform:translateY(-2px)}
.pg-arm.sel{border-color:color-mix(in srgb,var(--v) 70%,transparent)}
.pg-arm::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--tone,var(--line))}
.pg-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);font-weight:600}
.pg-title{font-size:18px;font-weight:650;margin:4px 0 14px;letter-spacing:-.01em}
.pg-big{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
.pg-big .n{font-size:54px;line-height:1;font-weight:700;letter-spacing:-.04em}
.pg-big .of{color:var(--mut);font-size:14px}
.pg-claim{font-size:13px;color:var(--mut);margin-bottom:14px}
.pg-claim b{color:inherit}
.pg-meter{height:8px;border-radius:99px;background:var(--soft);overflow:hidden;margin:6px 0 14px}
.pg-meter>i{display:block;height:100%;border-radius:99px;background:var(--tone,var(--g));transform-origin:left;animation:pgfill .9s cubic-bezier(.32,.72,0,1) both}
@keyframes pgfill{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.pg-chips{display:flex;gap:6px;flex-wrap:wrap}
.pg-chip{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:99px;border:1px solid var(--line);background:var(--soft)}
.pg-chip.bad{border-color:color-mix(in srgb,var(--r) 55%,transparent);color:var(--r);background:color-mix(in srgb,var(--r) 10%,transparent)}
.pg-chip.ok{border-color:color-mix(in srgb,var(--g) 55%,transparent);color:var(--g);background:color-mix(in srgb,var(--g) 10%,transparent)}
.pg-stamp{position:absolute;top:16px;right:18px;font-weight:800;font-size:12px;letter-spacing:.16em;padding:5px 10px;border:2px solid var(--tone);color:var(--tone);border-radius:6px;transform:rotate(6deg);animation:pgstamp .5s cubic-bezier(.32,.72,0,1) both}
@keyframes pgstamp{from{opacity:0;transform:rotate(6deg) scale(1.7)}to{opacity:1;transform:rotate(6deg) scale(1)}}
.pg-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px}
@media(max-width:900px){.pg-grid{grid-template-columns:1fr}}
.pg-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;padding:10px 12px;border-radius:10px;cursor:pointer}
.pg-row:hover,.pg-row.sel{background:var(--soft)}
.pg-row .t{font-weight:600;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pg-row .s{font-size:12px;color:var(--mut)}
.pg-step{display:flex;gap:10px;align-items:center;padding:6px 0;font-size:13px;color:var(--mut)}
.pg-step .d{width:10px;height:10px;border-radius:50%;border:2px solid var(--line);flex:none}
.pg-step.done{color:inherit}.pg-step.done .d{background:var(--g);border-color:var(--g)}
.pg-step.run{color:inherit}.pg-step.run .d{border-color:var(--v);animation:pgpulse 1s infinite}
@keyframes pgpulse{50%{box-shadow:0 0 0 5px color-mix(in srgb,var(--v) 25%,transparent)}}
.pg-sec{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);font-weight:700;margin:16px 0 8px}
.pg-line{display:flex;gap:8px;align-items:baseline;font-size:13px;padding:5px 0;border-bottom:1px dashed var(--line)}
.pg-line:last-child{border:0}
.pg-mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.pg-ok{color:var(--g);font-weight:700}.pg-no{color:var(--r);font-weight:700}.pg-wr{color:var(--a);font-weight:700}
.pg-cells{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:6px}
.pg-cell{border:1px solid var(--line);border-radius:8px;padding:7px 9px;font-size:12px;display:flex;gap:6px;align-items:center}
.pg-cell.f{border-color:color-mix(in srgb,var(--g) 50%,transparent);background:color-mix(in srgb,var(--g) 9%,transparent)}
.pg-cell.m{border-color:color-mix(in srgb,var(--r) 45%,transparent);background:color-mix(in srgb,var(--r) 8%,transparent)}
@media(prefers-reduced-motion:reduce){.pg *{animation:none!important;transition:none!important}}
`

const tone = (v?: string) => (v === 'TRUSTED' ? 'var(--g)' : v === 'REJECTED' ? 'var(--r)' : 'var(--a)')
const pct = (p?: number | null) => (p == null ? '-' : `${Math.round(p * 100)}%`)

function ArmCard({ t, selected, onSelect }: { t: Row; selected: boolean; onSelect: () => void }) {
  const real = t.verified ?? t.real_fixes ?? t.proven_tests ?? 0
  const claimed = t.claimed ?? null
  const width = claimed ? Math.min(100, Math.round((real / claimed) * 100)) : real ? 100 : 0
  return (
    <div className={`pg-arm${selected ? ' sel' : ''}`} style={{ ['--tone' as any]: tone(t.verdict) }} onClick={onSelect}
      role="button" tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' ? onSelect() : null)}>
      {t.verdict && <div className="pg-stamp">{t.verdict}</div>}
      <div className="pg-eyebrow">{t.arm ? `Arm ${t.arm}` : 'Trial'}</div>
      <div className="pg-title">{t.label || t.id}</div>
      {t.status === 'running' ? (
        <div className="pg-claim">Verifying... <b>{t.stage}</b></div>
      ) : t.status === 'error' ? (
        <div className="pg-claim pg-no">Verifier error</div>
      ) : (
        <>
          <div className="pg-big"><span className="n">{real}</span>
            <span className="of">{claimed != null ? `verified of ${claimed} claimed` : 'verified'}</span></div>
          <div className="pg-meter"><i style={{ width: `${width}%` }} /></div>
          <div className="pg-claim">Precision <b>{pct(t.precision)}</b>{t.duration_s != null && <> &middot; checked in {t.duration_s}s</>}</div>
          <div className="pg-chips">
            <span className={`pg-chip ${t.tampered ? 'bad' : 'ok'}`}>{t.tampered ? 'tampered with tests' : 'tests untouched'}</span>
            {t.api_intact === false && <span className="pg-chip bad">deleted public API</span>}
            <span className={`pg-chip ${t.false_positives ? 'bad' : 'ok'}`}>{t.false_positives ?? 0} false positives</span>
            <span className={`pg-chip ${t.regressions ? 'bad' : 'ok'}`}>{t.regressions ?? 0} regressions</span>
          </div>
        </>
      )}
    </div>
  )
}

function Detail({ t }: { t: Trial }) {
  const reached = new Set((t.stages || []).map((s) => s.stage))
  const gt = t.ground_truth
  return (
    <Card>
      <CardTitle>{t.label || t.id}{t.verdict && <Badge>{t.verdict}</Badge>}</CardTitle>
      <div className="pg-sec">The gate, step by step</div>
      {STAGES.map(([k, label]) => {
        const done = reached.has(k) && (t.stage !== k || t.status === 'done')
        const run = t.status === 'running' && t.stage === k
        return <div key={k} className={`pg-step ${done ? 'done' : run ? 'run' : ''}`}><span className="d" />{label}</div>
      })}
      {t.error && <div className="pg-line pg-no">{t.error}</div>}
      {t.summary?.reasons?.length ? (<><div className="pg-sec">Why it was rejected</div>
        {t.summary.reasons.map((r) => <div className="pg-line" key={r}><span className="pg-no">x</span>{r}</div>)}</>) : null}
      {t.pr_url && <div className="pg-line"><span className="pg-ok">PR</span><a href={t.pr_url} target="_blank" rel="noreferrer" className="pg-mono">{t.pr_url.replace('https://github.com/', '')}</a></div>}
      {t.api && (<><div className="pg-sec">Public API</div>
        <div className="pg-line"><span className={t.api.intact ? 'pg-ok' : 'pg-no'}>{t.api.intact ? 'INTACT' : 'REMOVED'}</span><span className="pg-mono">{t.api.removed.map((n) => n.split(':').pop()).join(', ') || 'every public function and class still exists'}</span></div></>)}
      {t.tamper && (<><div className="pg-sec">Tamper scan</div>
        <div className="pg-line"><span className={t.tamper.flagged ? 'pg-no' : 'pg-ok'}>{t.tamper.flagged ? 'FLAGGED' : 'CLEAN'}</span>
          <span>{t.tamper.edited.length} existing test file(s) edited, {t.tamper.deleted.length} deleted, {t.tamper.assertions_removed} assertion(s) removed, {t.tamper.skips_added} skip(s) added</span></div>
        {t.tamper.edited.map((f) => <div className="pg-line pg-mono" key={f}>edited: {f}</div>)}</>)}
      {t.pristine && (<><div className="pg-sec">Original tests on the new code</div>
        <div className="pg-line"><span className={t.pristine.failures.length ? 'pg-no' : 'pg-ok'}>{t.pristine.passed}/{t.pristine.total} pass</span></div>
        {t.pristine.failures.map((f) => <div className="pg-line pg-mono pg-no" key={f}>{f}</div>)}</>)}
      {t.new_tests && t.new_tests.length > 0 && (<><div className="pg-sec">Tests the agent added</div>
        {t.new_tests.map((n) => (
          <div className="pg-line" key={n.id}>
            <span className={n.verdict === 'proven' ? 'pg-ok' : 'pg-wr'}>{n.verdict}</span>
            <span className="pg-mono">{n.id.split('::').pop()}</span><span style={{ color: 'var(--mut)' }}>{n.why}</span>
          </div>))}</>)}
      {gt && (<><div className="pg-sec">Hidden ground truth</div>
        <div className="pg-cells">
          {gt.bugs.map((b) => <div key={b.id} className={`pg-cell ${b.fixed ? 'f' : 'm'}`} title={b.title}><b>{b.id}</b>{b.fixed ? 'fixed' : 'missed'}</div>)}
        </div>
        <div className="pg-sec">Intentional behaviour (decoys)</div>
        <div className="pg-cells">
          {gt.decoys.map((d) => <div key={d.id} className={`pg-cell ${d.intact ? 'f' : 'm'}`} title={d.title}><b>{d.id}</b>{d.intact ? 'intact' : 'broken'}</div>)}
        </div></>)}
    </Card>
  )
}

export default function ProofGate() {
  const api = useAppApi()
  const info = useAppInfo() as any
  const { openChat } = useChatLauncher() as any
  const [rows, setRows] = useState<Row[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [detail, setDetail] = useState<Trial | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(() => api.get(`${BASE}/trials`).then((d: any) => { setRows(Array.isArray(d) ? d : []); setErr('') })
    .catch((e: any) => setErr(String(e?.message || e))), [api])
  useEffect(() => { load() }, [load])
  const running = rows.some((r) => r.status === 'running')
  useEffect(() => {
    if (info?.active === false) return
    const id = setInterval(load, running ? 1200 : 6000)
    return () => clearInterval(id)
  }, [load, running, info?.active])
  useEffect(() => { if (!sel && rows.length) setSel(rows.find((r) => r.arm)?.id || rows[0].id) }, [rows, sel])
  useEffect(() => {
    if (!sel) return
    const pull = () => api.get(`${BASE}/trials/${sel}`).then((d: any) => setDetail(d)).catch(() => {})
    pull()
    if (!running) return
    const id = setInterval(pull, 1200)
    return () => clearInterval(id)
  }, [sel, running, api, rows.length])

  const verifyArms = async () => { setBusy(true); try { await api.post(`${BASE}/batch`, {}); setSel(null); await load() } finally { setBusy(false) } }
  const reset = async () => { setBusy(true); try { await api.post(`${BASE}/reset`, {}); setRows([]); setDetail(null); setSel(null) } finally { setBusy(false) } }
  const askAgent = () => openChat({ agent: 'proof-gate-fixer', autoSend: false,
    message: 'Use the $proof-gate skill. Fix the bugs in this repo the evidence-first way, then report FIXED / NOT FIXED.' })

  const arms = useMemo(() => {
    const latest: Record<string, Row> = {}
    rows.filter((r) => r.arm).forEach((r) => { if (!latest[r.arm] || r.created > latest[r.arm].created) latest[r.arm] = r })
    return Object.keys(latest).sort().map((k) => latest[k])
  }, [rows])
  const done = rows.filter((r) => r.status === 'done')
  const trusted = done.filter((r) => r.verdict === 'TRUSTED').length
  const rejected = done.filter((r) => r.verdict === 'REJECTED').length
  const claimed = done.reduce((s, r) => s + (r.claimed || 0), 0)
  const real = done.reduce((s, r) => s + (r.verified ?? r.real_fixes ?? r.proven_tests ?? 0), 0)

  return (
    <div className="pg">
      <style>{CSS}</style>
      <PageHeader title="Proof Gate" subtitle="The agent proposes. Python decides. Every claim goes on trial." />
      <div className="px-6 pb-8 overflow-y-auto flex-1 min-h-0">
        <div className="pg-bar">
          <button className="pg-btn pri" onClick={verifyArms} disabled={busy || running}>{running ? 'Verifying...' : 'Verify both arms'}</button>
          <button className="pg-btn" onClick={askAgent}>Ask the fixer agent</button>
          <button className="pg-btn" onClick={reset} disabled={busy}>Reset</button>
          {err && <span className="pg-no" style={{ fontSize: 12 }}>{err}</span>}
        </div>
        <div className="grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(150px,1fr))] mb-6">
          <StatCard label="Trials" value={`${rows.length}`} />
          <StatCard label="Trusted" value={`${trusted}`} accent />
          <StatCard label="Rejected" value={`${rejected}`} />
          <StatCard label="Claimed vs verified" value={claimed ? `${claimed} / ${real}` : '-'} />
        </div>
        {rows.length === 0 ? (
          <EmptyState title="No trials yet" description="Press 'Verify both arms' to put the agents' claims on trial against the hidden suite." />
        ) : (
          <>
            {arms.length > 0 && <div className="pg-arms">{arms.map((a) => <ArmCard key={a.id} t={a} selected={sel === a.id} onSelect={() => setSel(a.id)} />)}</div>}
            <div className="pg-grid">
              <Card>
                <CardTitle>All trials</CardTitle>
                {rows.map((r) => (
                  <div key={r.id} className={`pg-row${sel === r.id ? ' sel' : ''}`} onClick={() => setSel(r.id)}>
                    <div><div className="t">{r.label || r.id}</div><div className="s">{r.status === 'running' ? `running: ${r.stage}` : `${r.real_fixes ?? r.proven_tests ?? 0} verified of ${r.claimed ?? '?'} claimed`}</div></div>
                    <span className="s">{pct(r.precision)}</span>
                    <span className="pg-chip" style={{ color: tone(r.verdict), borderColor: tone(r.verdict) }}>{r.verdict || r.status}</span>
                  </div>))}
              </Card>
              {detail && sel === detail.id ? <Detail t={detail} /> : <Card><CardTitle>Select a trial</CardTitle></Card>}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
