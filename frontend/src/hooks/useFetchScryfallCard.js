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
    mutationFn: async (params) => {
      const res = await api.get('/fetch_card', { params });
      console.log("[FetchCard] Response:", res.data);
      if (!res.data?.scryfall) {
        throw new Error('Missing Scryfall data in response');
      }
      return res.data;
    },
    onSuccess: (data) => {
      console.log("[FetchCard] onSuccess triggered");
      onSuccess(data);
    },
    onError: (error) => {
      console.log("[FetchCard] onError triggered");
      onError(error);
    },
    onSettled: () => {
      console.log("[FetchCard] onSettled triggered");
    }
  });
};