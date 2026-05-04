import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_KEY = 'haven_token';
const USER_KEY  = 'haven_user';

export type User = {
  id: string;
  email: string;
  first_name?: string;
  kyc_status: 'pending' | 'approved' | 'rejected';
};

export async function saveSession(token: string, user: User) {
  await Promise.all([
    AsyncStorage.setItem(TOKEN_KEY, token),
    AsyncStorage.setItem(USER_KEY, JSON.stringify(user)),
  ]);
}

export async function loadSession(): Promise<{ token: string; user: User } | null> {
  const [token, userJson] = await Promise.all([
    AsyncStorage.getItem(TOKEN_KEY),
    AsyncStorage.getItem(USER_KEY),
  ]);
  if (!token || !userJson) return null;
  return { token, user: JSON.parse(userJson) };
}

export async function clearSession() {
  await Promise.all([
    AsyncStorage.removeItem(TOKEN_KEY),
    AsyncStorage.removeItem(USER_KEY),
  ]);
}
