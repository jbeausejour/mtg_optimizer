import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode }from 'jwt-decode';
import api from './api';
import SetupAxiosInterceptors from './AxiosConfig';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  // Helper function to check if token is expiring soon
  const isTokenExpiringSoon = (decodedToken) => {
    const currentTime = Date.now();
    const tokenExpiryTime = decodedToken.exp * 1000;
    const gracePeriod = 5 * 60 * 1000; // 5 minutes
    return tokenExpiryTime - currentTime < gracePeriod;
  };

  // Function to check token and refresh it if necessary
  const checkToken = async () => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      try {
        const decodedToken = jwtDecode(token);

        if (isTokenExpiringSoon(decodedToken)) {
          try {
            await refreshToken();  // Refresh the token if it's expiring soon
          } catch (error) {
            console.error('Token refresh failed:', error);
            logout();  // Log out if the token refresh fails
          }
        } else if (decodedToken.exp * 1000 > Date.now()) {
          console.info('Token is valid, set user');
          setUser(decodedToken);  // Token is valid, set user
        } else {
          console.info('Token expired, log out user');
          localStorage.removeItem('accessToken');
          logout();  // Token expired, log out user
        }
      } catch (error) {
        console.error('Invalid token:', error);
        localStorage.removeItem('accessToken');
        logout();
      }
    }
  };

  const login = async (credentials) => {
    try {
      const response = await api.post('/login', credentials);
      const { access_token, userId } = response.data; // Assume the response contains userId
      localStorage.setItem('accessToken', access_token);
      const decodedToken = jwtDecode(access_token);
      setUser({ ...decodedToken, userId }); // Set user with userId
      return userId; // Return userId
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const refreshToken = async () => {
    try {
      const response = await api.post('/refresh-token', {}, {
        headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
      });
      const { accessToken } = response.data;
      localStorage.setItem('accessToken', accessToken);
      const decodedToken = jwtDecode(accessToken);
      setUser(decodedToken);
      return decodedToken;
    } catch (error) {
      console.error('Failed to refresh token', error);
      logout();
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('accessToken');
    setUser(null);
  };

  // Call SetupAxiosInterceptors inside useEffect
  useEffect(() => {
    SetupAxiosInterceptors(checkToken, refreshToken, logout);
  }, [checkToken, refreshToken, logout]);

  const value = {
    user,
    login,
    logout,
    refreshToken,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
