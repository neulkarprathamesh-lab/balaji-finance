import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bc_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('bc_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
export { API };
