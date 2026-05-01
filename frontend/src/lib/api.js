import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

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
