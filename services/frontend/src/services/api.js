// services/frontend/src/services/api.js
import axios from 'axios';
import { injectTraceContext } from './tracing';

// Create axios instance with base URL
const api = axios.create({
  baseURL: '/api'
});

// Helper to generate correlation IDs
function generateCorrelationId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Add request interceptor for authentication and tracing
api.interceptors.request.use(config => {
  // Add token to all requests if available
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Add trace context to headers
  injectTraceContext(config.headers);
  
  // Generate and add correlation ID if not present
  if (!config.headers['X-Correlation-ID']) {
    config.headers['X-Correlation-ID'] = generateCorrelationId();
  }
  
  // Debug logs for development
  console.debug(`[API Request] ${config.method.toUpperCase()} ${config.url}`);
  
  return config;
}, 
error => {
  console.error('Request interceptor error:', error);
  return Promise.reject(error);
});

// Add response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => {
    // Store correlation ID for potential future use
    const correlationId = response.headers['x-correlation-id'];
    if (correlationId) {
      // Store for debugging/logging
      window.__lastCorrelationId = correlationId;
    }
    
    // Debug logs for development
    console.debug(`[API Response] ${response.status} from ${response.config.url}`);
    return response;
  },
  (error) => {
    // Store correlation ID even on error response
    if (error.response?.headers['x-correlation-id']) {
      window.__lastCorrelationId = error.response.headers['x-correlation-id'];
    }
    
    // Handle authentication errors
    if (error.response && error.response.status === 401) {
      // Clear token and redirect to login on auth error
      console.warn('Authentication error - redirecting to login');
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    
    // Log full error details for easier debugging
    console.error(`API Error (${error.response ? error.response.status : 'network error'})`, {
      url: error.config ? error.config.url : 'unknown',
      method: error.config ? error.config.method : 'unknown',
      correlationId: error.response?.headers['x-correlation-id'] || 'none',
      data: error.response ? error.response.data : null,
      error: error.message
    });
    
    return Promise.reject(error);
  }
);

export default api;
