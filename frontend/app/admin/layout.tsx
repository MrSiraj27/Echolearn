"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect } from "react";
import { ShieldAlert, Users, Activity, Flag, Settings, LogOut, CreditCard, Ban } from "lucide-react";
import { AdminAuthProvider, useAdminAuth } from "@/lib/admin-auth-context";

const NAV_ITEMS = [
  { href: "/admin/users", label: "Users", icon: Users, roles: ["superadmin", "support", "moderator"] },
  { href: "/admin/plans", label: "Plans", icon: CreditCard, roles: ["superadmin", "support"] },
  { href: "/admin/blocked-users", label: "Blocked Users", icon: Ban, roles: ["superadmin", "support", "moderator"] },
  { href: "/admin/system", label: "System Health", icon: Activity, roles: ["superadmin", "support", "moderator"] },
  { href: "/admin/moderation", label: "Moderation", icon: Flag, roles: ["superadmin", "support", "moderator"] },
  { href: "/admin/config", label: "Configuration", icon: Settings, roles: ["superadmin"] },
];

function AdminShell({ children }: { children: React.ReactNode }) {
  const { admin, isLoading, isAuthenticated, logout } = useAdminAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoginPage = pathname === "/admin/login";

  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isLoginPage) {
      // Redirect away quietly — never show a "permission denied" page that confirms
      // the route exists to someone who isn't an authenticated admin.
      router.replace("/admin/login");
    }
  }, [isLoading, isAuthenticated, isLoginPage, router]);

  if (isLoginPage) return <>{children}</>;

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white dark:bg-neutral-950">
        <div className="h-6 w-6 rounded-full border-2 border-neutral-200 dark:border-neutral-800 border-t-neutral-900 dark:border-t-neutral-100 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-white dark:bg-neutral-950 flex flex-col">
      <div className="bg-neutral-900 text-white px-4 py-2 flex items-center justify-center gap-2 text-xs font-medium">
        <ShieldAlert className="h-3.5 w-3.5" />
        You are logged in as ADMIN ({admin?.admin_role}) — {admin?.email}
      </div>

      <div className="flex flex-1 min-h-0">
        <aside className="w-56 shrink-0 border-r border-neutral-200 dark:border-neutral-800 flex flex-col">
          <div className="px-4 py-4">
            <p className="text-sm font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              EchoLearn Admin
            </p>
          </div>
          <nav className="flex-1 px-3 space-y-1">
            {NAV_ITEMS.filter((item) => !admin?.admin_role || item.roles.includes(admin.admin_role)).map((item) => {
              const Icon = item.icon;
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 text-sm px-2.5 py-2 rounded-lg transition-colors ${
                    active
                      ? "bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 font-medium"
                      : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="px-3 py-3 border-t border-neutral-200 dark:border-neutral-800">
            <button
              onClick={() => {
                logout();
                router.push("/admin/login");
              }}
              className="w-full flex items-center gap-2 text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 px-1 py-1 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </aside>
        <main className="flex-1 min-w-0 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminAuthProvider>
      <AdminShell>{children}</AdminShell>
    </AdminAuthProvider>
  );
}
