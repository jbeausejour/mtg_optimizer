import axios from 'axios';

const SetupAxiosInterceptors = (refreshToken, logout) => {
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
          logout();
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );
};

export default SetupAxiosInterceptors;