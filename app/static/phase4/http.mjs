const MESSAGES = Object.freeze({
  0: 'Koneksi atau respons belum dapat dipastikan. Periksa state terbaru sebelum melanjutkan.',
  400: 'Aksi ini tidak legal pada state sekarang. Pilih aksi dari meja terbaru.',
  401: 'Sesi browser tidak tersedia atau kedaluwarsa. Muat ulang untuk memulai sesi baru.',
  403: 'Token keamanan sesi tidak sesuai. Muat ulang halaman sebelum mencoba lagi.',
  404: 'Round atau prediksi tidak tersedia. Round dapat kedaluwarsa atau hilang setelah server dimulai ulang.',
  409: 'Giliran sudah berubah. State terbaru dimuat; pilih keputusan Anda kembali.',
  413: 'Request melebihi batas ukuran. Muat ulang halaman dan coba kembali.',
  422: 'Data request tidak valid. Periksa pengaturan dan pilihan Anda.',
  429: 'Seluruh slot round sedang terpakai. Tunggu sebentar sebelum membuat round baru.',
  503: 'Layanan atau penyimpanan belum tersedia. Simpan belum dapat dikonfirmasi; periksa History atau coba prediksi pada giliran yang sama.',
});
export function messageFor(error) { return MESSAGES[error?.status ?? 0] ?? 'Terjadi masalah pada server. Periksa state terbaru sebelum melanjutkan.'; }
export class HttpError extends Error {
  constructor(status) { super(messageFor({ status })); this.name = 'HttpError'; this.status = status; }
}

export function createHttpClient({ fetchImpl = globalThis.fetch, csrfToken = '', timeoutMs = 12000 } = {}) {
  let token = csrfToken;
  async function request(path, method = 'GET', payload, expectedStatus) {
    if (!path.startsWith('/api/')) throw new HttpError(0);
    const mutation = method !== 'GET';
    if (mutation && !token) throw new HttpError(401);
    const headers = { Accept: 'application/json' };
    if (mutation) { headers['Content-Type'] = 'application/json'; headers['X-CSRF-Token'] = token; }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(path, {
        method, headers, credentials: 'same-origin', redirect: 'error', signal: controller.signal,
        body: payload === undefined ? undefined : JSON.stringify(payload),
      });
      if (!response.ok) throw new HttpError(response.status);
      if (expectedStatus !== undefined && response.status !== expectedStatus) throw new HttpError(0);
      if (response.status === 204) return null;
      if (!response.headers.get('content-type')?.includes('application/json')) throw new HttpError(0);
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new HttpError(0);
      return data;
    } catch (error) {
      throw error instanceof HttpError ? error : new HttpError(0);
    } finally { clearTimeout(timer); }
  }
  const gamePath = id => '/api/games/' + encodeURIComponent(id);
  return {
    request,
    async getSession() {
      const data = await request('/api/session');
      if (typeof data.csrf_token !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(data.csrf_token)) throw new HttpError(0);
      token = data.csrf_token; return data;
    },
    createGame: payload => request('/api/games', 'POST', payload),
    getGame: id => request(gamePath(id)),
    action: (id, payload) => request(gamePath(id) + '/actions', 'POST', payload),
    predict: (id, payload) => request(gamePath(id) + '/predict', 'POST', payload),
    listPredictions: (limit = 20, offset = 0) => request('/api/predictions?limit=' + limit + '&offset=' + offset),
    getPrediction: id => request('/api/predictions/' + encodeURIComponent(id)),
    deletePrediction: id => request('/api/predictions/' + encodeURIComponent(id), 'DELETE', undefined, 204),
  };
}
