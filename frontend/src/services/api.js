import axios from 'axios';

export const fetchCardStats = async (cardName) => {
  try {
    const response = await axios.get(`${process.env.REACT_APP_API_URL}/card_stats/${cardName}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching card stats:', error);
    throw error;
  }
};