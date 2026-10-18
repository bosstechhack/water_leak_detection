import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export const fetchNetworkGraph = async () => {
  const response = await axios.get(`${API_URL}/network`);
  return response.data;
};

export const analyzeScenario = async (scenarioName: string) => {
  const response = await axios.get(`${API_URL}/analyze/${scenarioName}`);
  return response.data;
};
