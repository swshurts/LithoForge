import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// withCredentials makes axios include the session_token cookie on every
// request. Endpoints that don't need it (anonymous public ones like
// /upload, /optimize) work fine with the cookie present too.
export const api = axios.create({ baseURL: API, withCredentials: true });

export const fileToBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

export const uploadImage = async (file) => {
  const dataUrl = await fileToBase64(file);
  const { data } = await api.post("/upload", {
    image_base64: dataUrl,
    filename: file.name,
  });
  return data;
};

export const optimize = async (payload) => {
  const { data } = await api.post("/optimize", payload);
  return data;
};

export const getDefaultFilaments = async () => {
  const { data } = await api.get("/filaments/default");
  return data.filaments;
};

export const suggestPalette = async (imageId, paletteSize = 6, vibrancy = 0.0) => {
  const { data } = await api.post("/palette/suggest", {
    image_id: imageId,
    palette_size: paletteSize,
    vibrancy,
  });
  return data.filaments;
};

export const getFilamentLibrary = async () => {
  const { data } = await api.get("/filaments/library");
  return data.filaments;
};

// Manufacturer / private filament library (catalog of brand SKUs +
// closest-hex matcher + per-user private list + brand suggestions).
export const getManufacturerBrands = async () => {
  const { data } = await api.get("/filament-library/brands");
  return data.brands;
};

export const searchManufacturerByHex = async (
  hex,
  { algo = "de76", limit = 10, brand, includePrivate = false } = {},
) => {
  const params = { hex, algo, limit };
  if (brand) params.brand = brand;
  if (includePrivate) params.include_private = true;
  const { data } = await api.get("/filament-library/search", { params });
  return data;
};

export const listPrivateFilaments = async () => {
  const { data } = await api.get("/filament-library/mine");
  return data.filaments;
};

export const addPrivateFilament = async (payload) => {
  const { data } = await api.post("/filament-library/mine", payload);
  return data;
};

export const deletePrivateFilament = async (id) => {
  const { data } = await api.delete(`/filament-library/mine/${id}`);
  return data;
};

export const suggestFilament = async (payload) => {
  const { data } = await api.post("/filament-library/suggest", payload);
  return data;
};

// POST a palette → get a ranked "closest match" per filament against
// the user's private library (scope='mine'), the global manufacturer
// catalog (scope='manufacturer'), or both. Used by the LibraryMatchPanel
// to warn users when their palette can't be reproduced.
export const matchPalette = async (filaments, { scope = "mine", algo = "de2000" } = {}) => {
  const { data } = await api.post("/filament-library/match-palette", {
    filaments: filaments.map((f) => ({ hex: f.hex, name: f.name })),
    scope, algo,
  });
  return data;
};

export const exportUrl = (jobId, kind) => `${API}/export/${jobId}/${kind}`;

// --- Cloud presets (authenticated) ----------------------------------
export const listCloudPresets = async () => {
  const { data } = await api.get("/presets", { withCredentials: true });
  return data;
};

export const createCloudPreset = async (preset) => {
  const { data } = await api.post("/presets", preset, { withCredentials: true });
  return data;
};

export const deleteCloudPreset = async (presetId) => {
  await api.delete(`/presets/${presetId}`, { withCredentials: true });
};

export const importCloudPresets = async (presets) => {
  const { data } = await api.post("/presets/import", presets, { withCredentials: true });
  return data;
};

// --- Marketplace (Phase A) ------------------------------------------
export const PLATFORM_FEE_PCT = 6.0;

export const publishListing = async (jobId, payload) => {
  const { data } = await api.put(`/my-jobs/${jobId}/listing`, payload, {
    withCredentials: true,
  });
  return data;
};

export const unpublishListing = async (jobId) => {
  await api.delete(`/my-jobs/${jobId}/listing`, { withCredentials: true });
};

export const getListingStatus = async (jobId) => {
  const { data } = await api.get(`/my-jobs/${jobId}/listing`, {
    withCredentials: true,
  });
  return data;
};

export const browseMarketplace = async ({ limit = 60, skip = 0 } = {}) => {
  const { data } = await api.get("/marketplace", {
    params: { limit, skip },
  });
  return data;
};

export const getListingDetail = async (jobId) => {
  const { data } = await api.get(`/marketplace/${jobId}`);
  return data;
};

export const getCreatorProfile = async (userId) => {
  const { data } = await api.get(`/creators/${userId}`);
  return data;
};

// --- Printer profiles ----------------------------------------------
export const listPrinters = async () => {
  const { data } = await api.get("/printers");
  return data.printers;
};

export const checkBedFit = async (printerId, widthMm, heightMm) => {
  const { data } = await api.get(`/printers/${printerId}/fit`, {
    params: { width_mm: widthMm, height_mm: heightMm },
  });
  return data;
};

// Creative-commons license presets used in PublishDialog.
export const LICENSE_PRESETS = [
  { id: "All Rights Reserved", label: "All Rights Reserved (default)" },
  { id: "Personal Use Only", label: "Personal Use Only" },
  { id: "CC0", label: "CC0 — Public Domain" },
  { id: "CC-BY", label: "CC-BY — Attribution" },
  { id: "CC-BY-SA", label: "CC-BY-SA — Attribution + ShareAlike" },
  { id: "CC-BY-NC", label: "CC-BY-NC — Non-Commercial" },
  { id: "CC-BY-NC-SA", label: "CC-BY-NC-SA — Non-Commercial + ShareAlike" },
  { id: "CC-BY-ND", label: "CC-BY-ND — No Derivatives" },
];

// --- User quota -----------------------------------------------------
export const getMyQuota = async () => {
  const { data } = await api.get("/me/quota", { withCredentials: true });
  return data; // { tier, period, period_key, limit, used, remaining, blocked }
};

// --- Creator payouts (Stripe Connect) -------------------------------
export const startPayoutOnboarding = async () => {
  const origin = window.location.origin;
  const { data } = await api.post(
    "/payouts/onboard",
    {
      return_url: `${origin}/?payouts=ok`,
      refresh_url: `${origin}/?payouts=refresh`,
    },
    { withCredentials: true },
  );
  return data; // { url, account_id, payouts_enabled }
};

export const getPayoutStatus = async () => {
  const { data } = await api.get("/payouts/status", {
    withCredentials: true,
  });
  return data; // { has_account, payouts_enabled, charges_enabled, details_submitted }
};

export const getPayoutTransactions = async () => {
  const { data } = await api.get("/payouts/transactions", {
    withCredentials: true,
  });
  return data; // { transactions, total_paid_usd, total_pending_usd }
};

// --- Marketplace Phase B: guest checkout ----------------------------
export const createCheckoutSession = async (jobId, buyerEmail) => {
  const { data } = await api.post(`/marketplace/${jobId}/checkout`, {
    job_id: jobId,
    buyer_email: buyerEmail,
    origin_url: window.location.origin,
  });
  return data; // { url, session_id }
};

export const getCheckoutStatus = async (sessionId) => {
  const { data } = await api.get(`/marketplace/checkout/status/${sessionId}`);
  return data; // { status, payment_status, amount_total, currency, job_id, download_token }
};

export const tokenExportUrl = (jobId, kind, token, printerId = null) => {
  const params = new URLSearchParams({ token });
  if (printerId) params.set("printer", printerId);
  return `${API}/export/${jobId}/${kind}?${params.toString()}`;
};
