// src/services/tracedApi.js
import axios from 'axios';
import { getTracer } from './tracing';
import api from './api';

// Create a tracer for API operations
const tracer = getTracer('api');

// Create traced API methods with full path corrections and explicit auth handling
const tracedApi = {
  // Health check endpoint - no auth required, no trailing slash
  getHealth: async () => {
    return tracer.startActiveSpan('api.getHealth', {}, async (span) => {
      try {
        const response = await api.get('/health');
        span.setAttribute('http.status_code', response.status);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  // External data endpoint - no auth required, no trailing slash
  getExternalData: async () => {
    return tracer.startActiveSpan('api.getExternalData', {}, async (span) => {
      try {
        const response = await api.get('/external-data');
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('data.source', response.data.source);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  // Users endpoints - auth required, WITH trailing slash
  getUsers: async () => {
    return tracer.startActiveSpan('api.getUsers', {}, async (span) => {
      try {
        // Get token from localStorage
        const token = localStorage.getItem('token');
        
        // Make request with explicit Authorization header and trailing slash
        const response = await api.get('/users/', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('users.count', response.data.length);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  createUser: async (userData) => {
    return tracer.startActiveSpan('api.createUser', {}, async (span) => {
      try {
        // Get token
        const token = localStorage.getItem('token');
        
        span.setAttribute('user.email', userData.email);
        span.setAttribute('user.username', userData.username);
        
        // Use trailing slash for users endpoint
        const response = await api.post('/users/', userData, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('user.id', response.data.id);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  // Items endpoints - auth required, WITH trailing slash
  getItems: async () => {
    return tracer.startActiveSpan('api.getItems', {}, async (span) => {
      try {
        // Get token from localStorage
        const token = localStorage.getItem('token');
        
        // Make request with explicit Authorization header and trailing slash
        const response = await api.get('/items/', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('items.count', response.data.length);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  createItem: async (itemData) => {
    return tracer.startActiveSpan('api.createItem', {}, async (span) => {
      try {
        // Get token
        const token = localStorage.getItem('token');
        
        span.setAttribute('item.name', itemData.name);
        span.setAttribute('item.owner_id', itemData.owner_id);
        
        // Use trailing slash for items endpoint
        const response = await api.post('/items/', itemData, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('item.id', response.data.id);
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  // Authentication endpoints - special handling
  login: async (username, password) => {
    return tracer.startActiveSpan('api.login', {}, async (span) => {
      try {
        span.setAttribute('auth.username', username);
        
        // Create form data (required for token endpoint format)
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        // Use the standard axios for the token endpoint (not our api instance)
        const response = await axios.post('/api/auth/token', formData);
        
        span.setAttribute('http.status_code', response.status);
        span.setAttribute('auth.success', true);
        
        // Store token in localStorage
        localStorage.setItem('token', response.data.access_token);
        
        return response.data;
      } catch (error) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', error.message);
        span.setAttribute('auth.success', false);
        throw error;
      } finally {
        span.end();
      }
    });
  },
  
  logout: () => {
    return tracer.startActiveSpan('api.logout', {}, (span) => {
      try {
        localStorage.removeItem('token');
        span.setAttribute('auth.logout', true);
      } finally {
        span.end();
      }
    });
  }
};

// Export the traced API as default
export default tracedApi;
