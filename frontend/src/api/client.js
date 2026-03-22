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
  watchlist: () => client.get('/market/watchlist'),
  searchInstruments: (q) => client.get('/market/instruments/search', { params: { q } }),
  fundamentals: (symbol) => client.get(`/market/fundamentals/${symbol}`),
  insights: (symbol, sector) =>
    client.get(`/market/insights/${symbol}`, { params: sector ? { sector } : {} }),
  news: (symbol) => client.get(`/market/news/${symbol}`),
}

// ── Ingestion ─────────────────────────────────────────
export const ingestionApi = {
  list: (symbol, docType) =>
    client.get('/ingestion/documents', { params: { symbol, doc_type: docType } }),
  getDocument: (documentId) =>
    client.get(`/ingestion/documents/${documentId}`),
  getPdf: (documentId) =>
    client.get(`/ingestion/documents/${documentId}/pdf`, { responseType: 'blob' }),
  delete: (documentId) =>
    client.delete(`/ingestion/documents/${documentId}`),
  process: (documentId) =>
    client.post(`/ingestion/documents/${documentId}/process`),
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
  availableDocuments: () => client.get('/rag/available-documents'),
  prepare: (documentIds) =>
    client.post('/rag/prepare', { document_ids: documentIds }),
  query: (question, documentIds, model, topK = 8) =>
    client.post('/rag/query', {
      question,
      document_ids: documentIds,
      model,
      top_k: topK,
    }),
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

// ── Scraper (Screener.in) ─────────────────────────────
export const scraperApi = {
  searchCompany: (query) =>
    client.get('/scraper/search-company', { params: { query } }),
  companyDocuments: (symbol) =>
    client.get('/scraper/company-documents', { params: { symbol } }),
  downloadSelected: (symbol, companyName, documents) =>
    client.post('/scraper/download-selected', { symbol, company_name: companyName, documents }),
  jobStatus: (jobId) =>
    client.get(`/scraper/status/${jobId}`),
}

// ── Credibility Sentiment ─────────────────────────────
export const credisentimentApi = {
  availableDocuments: () =>
    client.get('/credisentiment/available-documents'),
  analyzeSentiment: (documentIds) =>
    client.post('/credisentiment/analyze-sentiment', { document_ids: documentIds }),
  walkTheTalk: (claimsDocId, actualsDocId) =>
    client.post('/credisentiment/walk-the-talk', {
      claims_document_id: claimsDocId,
      actuals_document_id: actualsDocId,
    }),
  process: (documentId) =>
    client.post(`/credisentiment/process/${documentId}`),
  upload: (file, symbol, docType, fiscalQuarter, fiscalYear) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('symbol', symbol)
    fd.append('doc_type', docType)
    if (fiscalQuarter) fd.append('fiscal_quarter', fiscalQuarter)
    if (fiscalYear) fd.append('fiscal_year', fiscalYear)
    return client.post('/credisentiment/upload', fd)
  },
}

// ── Watchlist ────────────────────────────────────────
export const watchlistApi = {
  list: () => client.get('/watchlist/'),
  create: (name, isDefault = false) =>
    client.post('/watchlist/', { name, is_default: isDefault }),
  get: (id) => client.get(`/watchlist/${id}`),
  update: (id, data) => client.put(`/watchlist/${id}`, data),
  delete: (id) => client.delete(`/watchlist/${id}`),
  addItem: (id, symbol, notes) =>
    client.post(`/watchlist/${id}/items`, { symbol, notes }),
  updateItem: (id, itemId, notes) =>
    client.put(`/watchlist/${id}/items/${itemId}`, { notes }),
  removeItem: (id, symbol) =>
    client.delete(`/watchlist/${id}/items/${symbol}`),
  quotes: (id) => client.get(`/watchlist/${id}/quotes`),
  digest: (id) => client.get(`/watchlist/${id}/digest`),
}

export default client
