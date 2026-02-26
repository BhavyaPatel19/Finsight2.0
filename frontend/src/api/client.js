import axios from 'axios'

const API_BASE = '/api'

const client = axios.create({ baseURL: API_BASE })

// Attach JWT on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('fs_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401 → clear token and redirect to login
client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('fs_token')
      localStorage.removeItem('fs_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ─────────────────────────────────────────────
export const authApi = {
  register: (email, password) =>
    client.post('/auth/register', { email, password }),
  login: (email, password) =>
    client.post('/auth/login', { email, password }),
  me: () => client.get('/auth/me'),
}

// ── Zerodha ───────────────────────────────────────────
export const zerodhaApi = {
  loginUrl: () => client.get('/zerodha/login-url'),
  connectUrl: () => client.get('/zerodha/connect-url'),
  link: (requestToken) =>
    client.post('/zerodha/link', { request_token: requestToken }),
  sync: () => client.post('/zerodha/sync'),
  holdings: () => client.get('/zerodha/holdings'),
}

// ── Portfolio ─────────────────────────────────────────
export const portfolioApi = {
  holdings: () => client.get('/portfolio/holdings'),
  insights: () => client.get('/portfolio/insights'),
}

// ── Market Data ───────────────────────────────────────
export const marketApi = {
  quotes: (symbols) => client.get('/market/quotes', { params: { symbols } }),
  ltp: (symbols) => client.get('/market/ltp', { params: { symbols } }),
  history: (symbol, interval = 'day', from_date, to_date) =>
    client.get(`/market/history/${symbol}`, { params: { interval, from_date, to_date } }),
}

// ── Ingestion ─────────────────────────────────────────
export const ingestionApi = {
  list: (symbol, docType) =>
    client.get('/ingestion/documents', { params: { symbol, doc_type: docType } }),
  upload: (file, symbol, docType, fiscalQuarter, fiscalYear) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('symbol', symbol)
    fd.append('doc_type', docType)
    if (fiscalQuarter) fd.append('fiscal_quarter', fiscalQuarter)
    if (fiscalYear) fd.append('fiscal_year', fiscalYear)
    return client.post('/ingestion/documents/upload', fd)
  },
  run: (documentId) =>
    client.post('/ingestion/run', { document_id: documentId }),
}

// ── RAG ───────────────────────────────────────────────
export const ragApi = {
  query: (question, symbol, period, topK = 8) =>
    client.post('/rag/query', { question, symbol, period, top_k: topK }),
}

// ── Sentiment ─────────────────────────────────────────
export const sentimentApi = {
  history: (symbol) => client.get(`/sentiment/${symbol}`),
  recompute: (documentId) =>
    client.post(`/sentiment/recompute/${documentId}`),
}

// ── Credibility ───────────────────────────────────────
export const credibilityApi = {
  history: (symbol) => client.get(`/credibility/${symbol}`),
  recompute: (symbol, period) =>
    client.post(`/credibility/recompute/${symbol}/${period}`),
  extractClaims: (documentId) =>
    client.post(`/credibility/extract-claims/${documentId}`),
}

// ── Scraper ───────────────────────────────────────────
export const scraperApi = {
  searchCompany: (query) =>
    client.get('/scraper/search-company', { params: { query } }),
  filings: (symbol, scrip_code, category) =>
    client.get('/scraper/filings', { params: { symbol, scrip_code, category } }),
  download: (url, symbol, doc_type) =>
    client.post('/scraper/download', null, { params: { url, symbol, doc_type } }),
  autoFetch: () => client.post('/scraper/auto-fetch'),
}

export default client
