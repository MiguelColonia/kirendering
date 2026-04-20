import axios from "axios";

function resolveDefaultApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.location.origin) {
    return window.location.origin;
  }

  return "http://127.0.0.1:8000";
}

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = (
  configuredApiBaseUrl && configuredApiBaseUrl !== "/"
    ? configuredApiBaseUrl
    : resolveDefaultApiBaseUrl()
).replace(/\/$/, "");

export const API_WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    "Content-Type": "application/json",
  },
});
