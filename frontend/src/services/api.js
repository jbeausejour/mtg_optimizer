import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL;

export const fetchCardStats = async (cardName) => {
  try {
    const response = await axios.get(`${API_URL}/card_stats/${cardName}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching card stats:', error);
    throw error;
  }
};