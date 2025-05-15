import api from './api';

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};
// Setup Axios Interceptors
const SetupAxiosInterceptors = (checkToken, refreshToken, logout) => {
  api.interceptors.response.use(
    response => response,
    async error => {
      const originalRequest = error.config;

      // Prevent infinite refresh attempts
      if (
        error.response?.status === 401 &&
        !originalRequest._retry &&
        !originalRequest.url.includes('/refresh-token')
      ) {
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then(token => {
              originalRequest.headers.Authorization = 'Bearer ' + token;
              return api(originalRequest);
            })
            .catch(err => {
              return Promise.reject(err);
            });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const refreshedUser = await refreshToken();
          isRefreshing = false;
          processQueue(null, localStorage.getItem('accessToken'));
          originalRequest.headers.Authorization = 'Bearer ' + localStorage.getItem('accessToken');
          return api(originalRequest);
        } catch (refreshError) {
          isRefreshing = false;
          processQueue(refreshError, null);
          logout();  // log out on refresh failure
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );
}; 

export default SetupAxiosInterceptors;