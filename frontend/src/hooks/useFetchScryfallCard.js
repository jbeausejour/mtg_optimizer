import { useMutation } from '@tanstack/react-query';
import api from '../utils/api';
import { message } from 'antd';

export const useFetchScryfallCard = ({
  onSuccess = () => {},
  onError = (error) => {
    console.error('[Scryfall Fetch Error]', error);
    message.error('Failed to fetch card details.');
  }
} = {}) => {
  return useMutation({
    mutationFn: (params) => api.get('/fetch_card', { params }),
    onSuccess: (res) => {
      if (!res.data?.scryfall) throw new Error("Invalid card data");
      onSuccess(res.data);
    },
    onError,
  });
};