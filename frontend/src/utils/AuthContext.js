import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { jwtDecode }from 'jwt-decode';
import api from './api';
import SetupAxiosInterceptors from './AxiosConfig';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); 

  const isTokenExpiringSoon = (decodedToken) => {
    const currentTime = Date.now();
    const tokenExpiryTime = decodedToken.exp * 1000;
    const gracePeriod = 5 * 60 * 1000; // 5 minutes
    return tokenExpiryTime - currentTime < gracePeriod;
  };


  const logout = useCallback(() => {
    localStorage.removeItem('accessToken');
    setUser(null);
  }, []);


  const refreshToken = useCallback(async () => {
    try {
      const response = await api.post('/refresh-token', {}, {
        withCredentials: true,
        headers: {
          Authorization: `Bearer ${localStorage.getItem('refreshToken')}`
        }
      });
      const { access_token, refresh_token } = response.data;
      localStorage.setItem('accessToken', access_token);
      if (refresh_token) {
          localStorage.setItem('refreshToken', refresh_token);
      }
      const decodedToken = jwtDecode(accessToken);
      setUser(decodedToken);
      return decodedToken;
    } catch (error) {
      console.error('Failed to refresh token', error);
      logout();
      throw error;
    }
  }, [logout]);


  const checkToken = useCallback(async () => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      try {
        const decodedToken = jwtDecode(token);

        if (isTokenExpiringSoon(decodedToken)) {
          await refreshToken(); 
        } else if (decodedToken.exp * 1000 > Date.now()) {
          setUser(decodedToken); 
        } else {
          localStorage.removeItem('accessToken');
          logout(); 
        }
      } catch (error) {
        console.error('Invalid token:', error);
        localStorage.removeItem('accessToken');
        logout();
      } finally {
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, [refreshToken, logout]);

  useEffect(() => {
    checkToken();
  }, [checkToken]);

  useEffect(() => {
    SetupAxiosInterceptors(checkToken, refreshToken, logout);
  }, [checkToken, refreshToken, logout]);

  const login = async (credentials) => {
    try {
      const response = await api.post('/login', credentials);
      const { access_token, refresh_token } = response.data;
      localStorage.setItem('accessToken', access_token);
      localStorage.setItem('refreshToken', refresh_token);
      
      const decodedToken = jwtDecode(access_token);
      setUser(decodedToken);
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const value = {
    user,
    login,
    logout,
    refreshToken,
    isAuthenticated: !!user,
    loading,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
