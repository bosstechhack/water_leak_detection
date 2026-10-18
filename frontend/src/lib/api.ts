import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export const fetchNetworks = async () => {
  const response = await axios.get(`${API_URL}/networks`);
  return response.data;
};

export const fetchScenarios = async (network: string) => {
  const response = await axios.get(`${API_URL}/scenarios`, { params: { network } });
  return response.data;
};

export const fetchNetworkGraph = async (network: string = 'net3') => {
  const response = await axios.get(`${API_URL}/network`, { params: { network } });
  return response.data;
};

export const analyzeScenario = async (scenarioName: string, useDemandMeters: boolean = true) => {
  const response = await axios.get(`${API_URL}/analyze/${scenarioName}`, {
    params: { use_demand_meters: useDemandMeters },
  });
  return response.data;
};

export const fetchEvaluation = async () => {
  const response = await axios.get(`${API_URL}/evaluation`);
  return response.data;
};
