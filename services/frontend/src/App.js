import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import tracedApi from './services/tracedApi';
import { getTracer } from './services/tracing';
import Logo from './components/Logo';

// Create a tracer for the App component
const tracer = getTracer('App');

function App() {
  const [apiStatus, setApiStatus] = useState(null);
  const [externalData, setExternalData] = useState(null);
  const [users, setUsers] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '' });
  const [newItem, setNewItem] = useState({ name: '', description: '', price: 0, owner_id: 1 });

  const [token, setToken] = useState(localStorage.getItem('token'));
  const [showLogin, setShowLogin] = useState(!token);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [loginError, setLoginError] = useState('');

  // Handle login
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    
    try {
      // Use traced API for login
      const result = await tracedApi.login(loginForm.username, loginForm.password);
      setToken(result.access_token);
      setShowLogin(false);
      setLoginForm({ username: '', password: '' });
      
      // Now fetch data with the token
      fetchData(result.access_token);
    } catch (err) {
      console.error('Login error:', err);
      setLoginError('Invalid username or password');
    }
  };

  // Handle logout
  const handleLogout = () => {
    tracedApi.logout();
    setToken(null);
    setShowLogin(true);
    setUsers([]);
    setItems([]);
  };

  const fetchData = useCallback(async (currentToken) => {
    return tracer.startActiveSpan('fetchData', {}, async (span) => {
      try {
        span.setAttribute('token_present', !!currentToken);
        
        setLoading(true);
        setError(null);
        
        // Always fetch health status (not protected)
        console.log('Checking API health...');
        try {
          const apiStatus = await tracedApi.getHealth();
          console.log('API health response:', apiStatus);
          setApiStatus({
            status: apiStatus.status || 'unknown',
            version: apiStatus.version || '1.0.0',
            timestamp: new Date().toISOString(),
            components: {
              database: { 
                status: apiStatus.components?.database?.status || apiStatus.database || 'unknown' 
              },
              cache: { 
                status: apiStatus.components?.cache?.status || apiStatus.cache || 'unknown' 
              }
            },
            // Keep the original values accessible as well
            database: apiStatus.database || 'unknown',
            cache: apiStatus.cache || 'unknown'
          });
        } catch (err) {
          console.log('Health check failed:', err.message);
        }
        
        // Get external data (not protected)
        try {
          console.log('Fetching external data...');
          const externalData = await tracedApi.getExternalData();
          setExternalData(externalData);
        } catch (err) {
          console.log('External data not available:', err.message);
        }
        
        // Only fetch protected data if we have a token
        if (currentToken) {
          // Get users with better error handling
          console.log('Fetching users...');
          try {
            const users = await tracedApi.getUsers();
            // Ensure we have an array even if the API returned something else
            setUsers(Array.isArray(users) ? users : []);
          } catch (err) {
            console.error('Error fetching users:', err);
            setUsers([]);
          }
          
          // Get items with better error handling
          console.log('Fetching items...');
          try {
            const items = await tracedApi.getItems();
            // Ensure we have an array even if the API returned something else
            setItems(Array.isArray(items) ? items : []);
          } catch (err) {
            console.error('Error fetching items:', err);
            setItems([]);
          }
        }
        
        setLoading(false);
      } catch (err) {
        span.setAttribute('error', true);
        span.setAttribute('error.message', err.message);
        
        console.error('Error fetching data:', err);
        // Improved error handling
        if (err.response?.status === 401 || err.message?.includes('unauthorized')) {
          setError('Authentication required. Please log in.');
          setToken(null);
          localStorage.removeItem('token');
          setShowLogin(true);
        } else {
          setError(`Failed to fetch data: ${err.message}`);
        }
        setLoading(false);
      } finally {
        span.end();
      }
    });
  }, []);

  // Initial data fetch on component mount
  useEffect(() => {
    fetchData(token);
  }, [fetchData, token]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!token) {
      setError('Please log in to create a user');
      return;
    }
    
    try {
      const response = await tracedApi.createUser(newUser);
      setUsers([...users, response]);
      setNewUser({ username: '', email: '', password: '' });
      // Success notification
      setError(null);
    } catch (err) {
      console.error('Error creating user:', err);
      
      // Extract and display detailed validation errors
      if (err.response && err.response.status === 422 && err.response.data.detail) {
        const validationErrors = err.response.data.detail;
        
        // Format validation errors for display
        if (Array.isArray(validationErrors)) {
          const errorMessages = validationErrors.map(error => 
            `${error.loc.join('.')} - ${error.msg}`
          ).join('; ');
          setError(`Validation errors: ${errorMessages}`);
        } else {
          setError(`Failed to create user: ${JSON.stringify(err.response.data.detail)}`);
        }
      } else {
        // Generic error message fallback
        setError('Failed to create user: ' + (err.response?.data?.detail || err.message));
      }
    }
  };
  const handleCreateItem = async (e) => {
    e.preventDefault();
    if (!token) {
      setError('Please log in to create an item');
      return;
    }
    
    try {
      const response = await tracedApi.createItem(newItem);
      setItems([...items, response]);
      setNewItem({ name: '', description: '', price: 0, owner_id: 1 });
    } catch (err) {
      console.error('Error creating item:', err);
      setError('Failed to create item: ' + (err.response?.data?.detail || err.message));
    }
  };

  if (loading) return <div className="loader">Loading...</div>;

  // Login form
  if (showLogin) {
    return (
      <div className="App">
        <header className="App-header">
          <div className="header-branding">
            <Logo size={32} />
            <h1>Nexa API Center</h1>
          </div>
        </header>
        
        <section className="status-panel">
          <h2>System Status</h2>
          {apiStatus && (
            <div className="status-card">
              <div className="status-header">
                <h3>
                  <span className={`status-indicator ${
                    (apiStatus.components.database.status === "healthy" && 
                    apiStatus.components.cache.status === "healthy") 
                      ? "status-healthy" 
                      : "status-unhealthy"
                  }`}></span>
                  System Status: {apiStatus.status}
                </h3>
                <span className="status-version">v{apiStatus.version}</span>
              </div>
              <div className="status-details">
                <p>
                  <span>Database:</span> 
                  <span className={apiStatus.components.database.status === "healthy" ? "text-success" : "text-error"}>
                    {apiStatus.components.database.status}
                  </span>
                </p>
                <p>
                  <span>Cache:</span>
                  <span className={apiStatus.components.cache.status === "healthy" ? "text-success" : "text-error"}>
                    {apiStatus.components.cache.status}
                  </span>
                </p>
                <p className="status-timestamp">Last updated: {new Date(apiStatus.timestamp).toLocaleTimeString()}</p>
              </div>
            </div>
          )}
        </section>
        
        <div className="login-container">
          <div className="login-header">
            <h2>Welcome to Nexa API</h2>
            <p className="login-subtitle">Sign in to access your dashboard</p>
          </div>
          
          {loginError && (
            <div className="error-message">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              {loginError}
            </div>
          )}
          
          {error && <div className="error">{error}</div>}
          
          <form onSubmit={handleLogin} className="login-form">
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                value={loginForm.username}
                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                placeholder="Enter your username"
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                placeholder="Enter your password"
                required
              />
            </div>
            
            <button type="submit" disabled={loading}>
              {loading ? (
                <span className="loading-spinner"></span>
              ) : 'Sign In'}
            </button>
          </form>
          
          <div className="login-footer">
            <p>Default credentials: admin / admin123 </p>
          </div>
        </div>
        
        {externalData && (
          <section className="external-data-panel">
            <h2>External Data</h2>
            <div className="data-card">
              <p>Source: {externalData.source}</p>
              <pre>{JSON.stringify(externalData.data, null, 2)}</pre>
            </div>
          </section>
        )}
      </div>
    );
  }

  // Main dashboard (authenticated)
  return (
    <div className="App">
      <header className="App-header">
        <div className="header-branding">
          <Logo size={32} />
          <h1>Nexa API Center</h1>
        </div>
        <button onClick={handleLogout} className="logout-button">Logout</button>
      </header>
      
      <section className="status-panel">
        <h2>System Status</h2>
        {apiStatus && (
          <div className="status-card">
            <div className="status-header">
              <h3>
                <span className={`status-indicator ${apiStatus.database === "healthy" && apiStatus.cache === "healthy" ? "status-healthy" : "status-unhealthy"}`}></span>
                System Status: {apiStatus.status}
              </h3>
              <span className="status-version">v{apiStatus.version}</span>
            </div>
            <div className="status-details">
              <p>
                <span>Database:</span> 
                <span className={apiStatus.components.database.status === "healthy" ? "text-success" : "text-error"}>
                  {apiStatus.components.database.status}
                </span>
              </p>
              <p>
                <span>Cache:</span>
                <span className={apiStatus.components.cache.status === "healthy" ? "text-success" : "text-error"}>
                  {apiStatus.components.cache.status}
                </span>
              </p>
              <p className="status-timestamp">Last updated: {new Date(apiStatus.timestamp).toLocaleTimeString()}</p>
            </div>
          </div>
        )}
      </section>
      
      {error && <div className="error">{error}</div>}
      
      <section className="data-panel">
        <div className="column">
          <h2>Users</h2>
          <form onSubmit={handleCreateUser} className="create-form">
            <h3>Create New User</h3>
            
            <input
              type="text"
              placeholder="Username (minimum 3 characters)"
              value={newUser.username}
              onChange={(e) => setNewUser({...newUser, username: e.target.value})}
              required
              minLength="3"
            />
            
            <input
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={(e) => setNewUser({...newUser, email: e.target.value})}
              required
              pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"
            />
            
            <input
              type="password"
              placeholder="Password (minimum 8 characters)"
              value={newUser.password}
              onChange={(e) => setNewUser({...newUser, password: e.target.value})}
              required
              minLength="8"
            />
            
            <button type="submit">Create User</button>
          </form>
          
          <div className="list-container">
            {Array.isArray(users) && users.length > 0 ? (
              users.map((user) => (
                <div key={user.id} className="list-item">
                  <h4>{user.username}</h4>
                  <p>Email: {user.email}</p>
                  <p>ID: {user.id}</p>
                </div>
              ))
            ) : (
              <p>No users found.</p>
            )}
          </div>
        </div>
        
        <div className="column">
          <h2>Items</h2>
          <form onSubmit={handleCreateItem} className="create-form">
            <h3>Create New Item</h3>
            <input
              type="text"
              placeholder="Name"
              value={newItem.name}
              onChange={(e) => setNewItem({...newItem, name: e.target.value})}
              required
            />
            <input
              type="text"
              placeholder="Description"
              value={newItem.description}
              onChange={(e) => setNewItem({...newItem, description: e.target.value})}
            />
            <input
              type="number"
              placeholder="Price"
              value={newItem.price}
              onChange={(e) => setNewItem({...newItem, price: parseFloat(e.target.value)})}
              required
              step="0.01"
            />
            <input
              type="number"
              placeholder="Owner ID"
              value={newItem.owner_id}
              onChange={(e) => setNewItem({...newItem, owner_id: parseInt(e.target.value)})}
              required
            />
            <button type="submit">Create Item</button>
          </form>
          
          <div className="list-container">
            {Array.isArray(items) && items.length > 0 ? (
              items.map((item) => (
                <div key={item.id} className="list-item">
                  <h4>{item.name}</h4>
                  <p>{item.description}</p>
                  <p>Price: ${item.price.toFixed(2)}</p>
                  <p>Owner ID: {item.owner_id}</p>
                </div>
              ))
            ) : (
              <p>No items found.</p>
            )}
          </div>
        </div>
      </section>
      
      {externalData && (
        <section className="external-data-panel">
          <h2>External Data</h2>
          <div className="data-card">
            <p>Source: {externalData.source}</p>
            <pre>{JSON.stringify(externalData.data, null, 2)}</pre>
          </div>
        </section>
      )}
    </div>
  );
}

export default App;
