// Recorded demo for static hosting (GitHub Pages).
//
// The full system needs a Python backend, three local models and an LLM provider, so the hosted
// build replays API responses recorded from a real local run instead of calling a server.
//
//   VITE_RECORD=1 npm run dev   → click through the app; a "Download recordings" button saves
//                                 every API response to finsight-recordings.json
//   VITE_DEMO=1 npm run build   → the build answers from public/demo/recordings.json
//
// Account-bound routes (auth, Zerodha, portfolio, watchlist) are never recorded, so the published
// file holds no personal data; the demo signs visitors in as a fixed demo user.

export const MODE =
  import.meta.env.VITE_DEMO === '1' ? 'demo' : import.meta.env.VITE_RECORD === '1' ? 'record' : 'live'

const PRIVATE = /^\/(auth|zerodha|portfolio|watchlist)(\/|$)/
const DEMO_USER = { id: 0, first_name: 'Demo', last_name: 'Visitor', email: 'demo@finsight.example', created_at: '2026-01-01T00:00:00Z', last_login_at: null }

const canon = (v) => {
  if (v === undefined || v === null || v === '') return ''
  if (typeof v === 'string') { try { return canon(JSON.parse(v)) } catch { return v } }
  if (Array.isArray(v)) return JSON.stringify(v.map((x) => (typeof x === 'object' ? JSON.parse(canon(x) || 'null') : x)))
  if (typeof v === 'object') {
    const out = {}
    for (const k of Object.keys(v).sort()) if (v[k] !== undefined) out[k] = v[k]
    return JSON.stringify(out)
  }
  return String(v)
}
const pathOf = (config) => (config.url || '').split('?')[0]
const keyOf = (method, path, params, data) => `${method.toUpperCase()} ${path} ${canon(params)} ${canon(data)}`
const normQ = (q) => String(q || '').toLowerCase().replace(/\s+/g, ' ').trim()

// ── record mode ──────────────────────────────────────
function installRecorder(client) {
  const entries = []
  client.interceptors.response.use((r) => {
    const path = pathOf(r.config)
    if (!PRIVATE.test(path) && r.config.responseType !== 'blob' && !(r.config.data instanceof FormData)) {
      entries.push({
        method: r.config.method.toUpperCase(), path,
        params: r.config.params ?? null, data: r.config.data ? JSON.parse(r.config.data) : null,
        status: r.status, response: r.data,
      })
      btn.textContent = `Download recordings (${entries.length})`
    }
    return r
  })
  const btn = document.createElement('button')
  btn.textContent = 'Download recordings (0)'
  Object.assign(btn.style, {
    position: 'fixed', right: '16px', bottom: '16px', zIndex: 99999, padding: '10px 14px',
    borderRadius: '8px', border: '0', background: '#b3276c', color: '#fff', font: '600 13px system-ui', cursor: 'pointer',
  })
  btn.onclick = () => {
    const blob = new Blob([JSON.stringify({ recorded_at: new Date().toISOString(), entries }, null, 1)], { type: 'application/json' })
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'finsight-recordings.json' })
    a.click()
  }
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(btn))
  if (document.body) document.body.appendChild(btn)
}

// ── demo mode ────────────────────────────────────────
let store = null
function load() {
  if (!store) {
    store = fetch(`${import.meta.env.BASE_URL}demo/recordings.json`)
      .then((r) => (r.ok ? r.json() : { entries: [] }))
      .then(({ entries = [] }) => {
        const exact = new Map(), byPath = new Map(), byQuestion = new Map()
        for (const e of entries) {
          exact.set(keyOf(e.method, e.path, e.params, e.data), e)
          byPath.set(`${e.method} ${e.path}`, e) // last one wins
          if (e.path === '/rag/query' && e.data?.question) byQuestion.set(normQ(e.data.question), e)
        }
        return { exact, byPath, byQuestion }
      })
  }
  return store
}

/** Questions with recorded answers, for the Chat page's suggestions. */
export async function demoQuestions() {
  if (MODE !== 'demo') return []
  const { byQuestion } = await load()
  return [...byQuestion.values()].map((e) => e.data.question)
}

const SLOW = new Set(['/rag/query', '/rag/prepare', '/credisentiment/walk-the-talk', '/credisentiment/analyze-sentiment'])
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function respond(config, status, data) {
  const res = { data, status, statusText: String(status), headers: {}, config, request: {} }
  if (status >= 400) {
    const err = new Error(`Request failed with status code ${status}`)
    Object.assign(err, { config, response: res, isAxiosError: true })
    throw err
  }
  return res
}

async function demoAdapter(config) {
  const method = config.method.toUpperCase()
  const path = pathOf(config)
  const data = config.data ? JSON.parse(config.data) : null

  if (path === '/auth/login') return respond(config, 200, { access_token: 'demo', token_type: 'bearer' })
  if (path === '/auth/me') return respond(config, 200, DEMO_USER)

  const { exact, byPath, byQuestion } = await load()
  if (SLOW.has(path)) await wait(path === '/rag/query' ? 900 : 1200)

  const hit = exact.get(keyOf(method, path, config.params, data))
    || (path === '/rag/query' && byQuestion.get(normQ(data?.question)))
    || (method === 'GET' && byPath.get(`${method} ${path}`))
  if (hit) return respond(config, hit.status, hit.response)

  if (path === '/rag/query') {
    const qs = [...byQuestion.values()].map((e) => `• ${e.data.question}`).join('\n')
    return respond(config, 200, {
      answer: `This is a recorded demo, so only questions answered in the recorded run are available:\n\n${qs}\n\nRun FinSight locally to ask anything.`,
      sources: [], evidence: [], navigations: [], thinking: null, model_used: 'recorded demo',
    })
  }
  return respond(config, 503, { detail: 'Not part of the recorded demo. Run FinSight locally for this feature.' })
}

function showBanner() {
  const b = document.createElement('div')
  b.innerHTML = 'Recorded demo — answers, citations and verdicts are replayed from a real local run. ' +
    '<a href="https://github.com/BhavyaPatel19/Finsight2.0#quickstart" style="color:inherit;text-decoration:underline">Run it locally for live data →</a>'
  Object.assign(b.style, {
    position: 'fixed', left: '0', right: '0', bottom: '0', zIndex: 99999, padding: '8px 14px', textAlign: 'center',
    background: '#1f3a64', color: '#fff', font: '13px system-ui',
  })
  document.body.appendChild(b)
}

export function installMode(client) {
  if (MODE === 'record') installRecorder(client)
  if (MODE === 'demo') {
    client.defaults.adapter = demoAdapter
    localStorage.setItem('fs_token', 'demo')
    if (document.body) showBanner(); else document.addEventListener('DOMContentLoaded', showBanner)
  }
}
