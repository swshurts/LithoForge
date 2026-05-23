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
