import axios from 'axios'

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://127.0.0.1:8000'

export const API_WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws')

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: {
    'Content-Type': 'application/json',
  },
})