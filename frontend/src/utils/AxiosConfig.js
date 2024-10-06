import axios from 'axios';

// Setup Axios Interceptors
const SetupAxiosInterceptors = (checkToken, refreshToken, logout) => {
  // Request Interceptor: check the token before each request
  axios.interceptors.request.use(
    async (config) => {
      try {
        // Call checkToken to ensure it's valid or refreshed
        await checkToken();
        const token = localStorage.getItem('accessToken');
        if (token) {
          config.headers['Authorization'] = `Bearer ${token}`;
        }
      } catch (error) {
        console.error('Token validation failed:', error);
        logout();  // Log out if token validation or refresh fails
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response Interceptor: Handle 401 Unauthorized errors
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          await refreshToken();
          originalRequest.headers['Authorization'] = `Bearer ${localStorage.getItem('accessToken')}`;
          return axios(originalRequest);
        } catch (refreshError) {
          // Instead of logging out immediately, provide a message or redirect to the login page
          console.error('Token refresh failed. Please log in again.');
          // Optionally redirect to login page
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );
};

export default SetupAxiosInterceptors;