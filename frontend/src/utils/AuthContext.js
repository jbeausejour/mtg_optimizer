import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import api from './api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      try {
        const decodedToken = jwtDecode(token);
        if (decodedToken.exp * 1000 > Date.now()) {
          setUser(decodedToken);
        } else {
          localStorage.removeItem('accessToken');
        }
      } catch (error) {
        console.error('Invalid token', error);
        localStorage.removeItem('accessToken');
      }
    }
  }, []);

  const login = async (credentials) => {
    try {
      const response = await api.post('/login', credentials);
      console.log('Server response:', response.data); // For debugging

      const { access_token } = response.data;

      if (!access_token || typeof access_token !== 'string' || access_token.trim() === '') {
        throw new Error('Invalid token received from server');
      }

      localStorage.setItem('accessToken', access_token);
      const decodedToken = jwtDecode(access_token);
      setUser(decodedToken);
      return decodedToken;
    } catch (error) {
      console.error('Login error:', error);
      if (error.response) {
        console.error('Server responded with:', error.response.data);
      }
      throw error;
    }
  };


  const logout = () => {
    localStorage.removeItem('accessToken');
    setUser(null);
  };

  const refreshToken = async () => {
    try {
      const response = await api.post('/refresh-token', {}, {
        headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` }
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

  const value = {
    user,
    login,
    logout,
    refreshToken,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={{ user, login, logout, refreshToken, isAuthenticated: !!user }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);