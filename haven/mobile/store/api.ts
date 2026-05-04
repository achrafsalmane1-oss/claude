import AsyncStorage from '@react-native-async-storage/async-storage';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:3000';

async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem('haven_token');
}

async function request(path: string, options: RequestInit = {}) {
  const token = await getToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

export const api = {
  signup: (email: string, password: string) =>
    request('/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: (email: string, password: string) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  initiateKyc: () =>
    request('/auth/kyc/initiate', { method: 'POST' }),

  getBalance: () =>
    request('/wallet/balance'),

  getTransactions: () =>
    request('/wallet/transactions'),

  createDepositIntent: (amountUsd: number) =>
    request('/deposit/stripe-intent', { method: 'POST', body: JSON.stringify({ amount_usd: amountUsd }) }),

  requestWithdrawal: (amountUsd: number) =>
    request('/withdraw/request', { method: 'POST', body: JSON.stringify({ amount_usd: amountUsd }) }),

  getWithdrawalStatus: (id: string) =>
    request(`/withdraw/status/${id}`),

  getYieldHistory: (days = 30) =>
    request(`/yield/history?days=${days}`),

  getCurrentApy: () =>
    request('/apy/current'),
};
