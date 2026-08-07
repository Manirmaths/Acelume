import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, ApiError } from '../api/client';
import type { User } from '../api/types';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Shown when the credentials were accepted but the session cookie did not
 * survive. See verifySession() below for why that can happen.
 */
export const SESSION_NOT_SAVED =
  "Your details were correct, but this app couldn't save your session. " +
  'If you are using the Acelume app, please update it to the latest version ' +
  'from the Play Store. On a browser, check that cookies are enabled.';

/**
 * Confirm the auth cookie actually persisted, rather than trusting the login
 * response body.
 *
 * A successful POST /api/auth/login returns 200 with the user regardless of
 * whether the browser accepted the Set-Cookie header. Those are genuinely
 * different outcomes, and treating them as one produced a real production
 * bug (2026-08-07): the Android build shipped to Play Store testing points at
 * naijaprep.com.ng while the API lives on api.acelume.ng. Those are different
 * registrable domains, so the request is CROSS-site, so a SameSite=Lax cookie
 * is silently dropped by the browser. Login "succeeded", the UI set a user,
 * RequireAuth let them through, and then every authenticated call 401'd --
 * surfacing to the student as "Couldn't load your dashboard" with no way to
 * recover and nothing to indicate they were not really signed in.
 *
 * One extra request at login is a cheap price for never showing a signed-in
 * shell backed by a dead session. This also covers the general cases: private
 * browsing, blocked third-party cookies, and Safari ITP.
 */
async function verifySession(): Promise<User> {
  try {
    return await api.get<User>('/api/auth/me');
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      throw new ApiError(401, SESSION_NOT_SAVED);
    }
    throw e;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const me = await api.get<User>('/api/auth/me');
      setUser(me);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUser(null);
      }
    }
  };

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    await api.post<User>('/api/auth/login', { email, password });
    setUser(await verifySession());
  };

  const register = async (username: string, email: string, password: string) => {
    await api.post<User>('/api/auth/register', { username, email, password });
    setUser(await verifySession());
  };

  const logout = async () => {
    await api.post('/api/auth/logout');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
