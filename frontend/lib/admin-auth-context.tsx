"use client";

import { createContext, useContext, useState, ReactNode, useEffect, useCallback } from "react";
import { adminApi, getAdminToken, setAdminToken } from "./admin-api";

interface AdminUser {
  id: string;
  name: string;
  email: string;
  admin_role: string | null;
}

interface AdminAuthContextValue {
  admin: AdminUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string, admin: AdminUser) => void;
  logout: () => void;
}

const AdminAuthContext = createContext<AdminAuthContextValue | undefined>(undefined);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAdminToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    adminApi
      .get<AdminUser>("/admin/auth/me")
      .then(setAdmin)
      .catch(() => setAdminToken(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback((token: string, adminUser: AdminUser) => {
    setAdminToken(token);
    setAdmin(adminUser);
  }, []);

  const logout = useCallback(() => {
    setAdminToken(null);
    setAdmin(null);
  }, []);

  return (
    <AdminAuthContext.Provider value={{ admin, isLoading, isAuthenticated: !!admin, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error("useAdminAuth must be used within AdminAuthProvider");
  return ctx;
}
