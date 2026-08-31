"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { setAccessToken, tryRefresh } from "./api";

const SESSION_HINT_KEY = "echolearn_had_session";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Only attempt a silent refresh if we have reason to believe a session might
    // exist — avoids a guaranteed, console-visible 401 on every first visit.
    let hadSession = false;
    try {
      hadSession = localStorage.getItem(SESSION_HINT_KEY) === "1";
    } catch {
      // localStorage unavailable (e.g. private mode) — fall through to no session.
    }

    if (!hadSession) {
      setIsLoading(false);
      return;
    }

    tryRefresh().then((ok) => {
      setIsAuthenticated(ok);
      setIsLoading(false);
      if (!ok) {
        try {
          localStorage.removeItem(SESSION_HINT_KEY);
        } catch {
          // ignore
        }
      }
    });
  }, []);

  const login = useCallback((token: string) => {
    setAccessToken(token);
    setIsAuthenticated(true);
    try {
      localStorage.setItem(SESSION_HINT_KEY, "1");
    } catch {
      // ignore
    }
  }, []);

  const logout = useCallback(() => {
    setAccessToken(null);
    setIsAuthenticated(false);
    try {
      localStorage.removeItem(SESSION_HINT_KEY);
    } catch {
      // ignore
    }
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
