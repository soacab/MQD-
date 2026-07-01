"use client";

import { FileText, ListChecks, Plus, Settings } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser } from "@/lib/session";
import type { User } from "@/lib/api";

const navItems = [
  { href: "/", label: "工作台" },
  { href: "/rules", label: "规则配置", icon: ListChecks },
  { href: "/reports", label: "检查档案", icon: FileText }
];

function isActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(href);
}

function userInitial(user: User | null) {
  return (user?.name || user?.uid || "账").slice(0, 1);
}

export function AppNav() {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    function syncStoredUser() {
      setUser(getStoredUser());
    }
    syncStoredUser();
    window.addEventListener("checkflow:session-changed", syncStoredUser);
    return () => window.removeEventListener("checkflow:session-changed", syncStoredUser);
  }, []);

  const canCreateTask = Boolean(user?.permissions.includes("inspection_engineer"));
  const canOpenAdmin = Boolean(user?.permissions.some((permission) => permission === "super_admin"));

  function openNewTaskModal() {
    if (pathname === "/") {
      window.dispatchEvent(new CustomEvent("checkflow:new-task"));
      return;
    }
    window.location.href = "/?new_task=1";
  }

  return (
    <header className="app-topbar">
      <a className="app-brand" href="/" aria-label="CheckFlow 工作台">
        <span className="app-logo">✓</span>
        <span className="app-brand-text">CheckFlow</span>
      </a>
      <nav className="app-nav" aria-label="主导航">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <a className={isActive(pathname, item.href) ? "active" : ""} href={item.href} key={item.href}>
              {Icon ? <Icon aria-hidden="true" size={15} strokeWidth={2} /> : null}
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>
      <div className="app-topbar-actions">
        {canCreateTask ? (
          <button className="app-create-task" type="button" onClick={openNewTaskModal}>
            <Plus aria-hidden="true" size={16} strokeWidth={2.4} />
            <span>+ 新建任务</span>
          </button>
        ) : (
          <span className="app-create-task disabled" title="当前账号没有点检执行权限" aria-disabled="true">
            <Plus aria-hidden="true" size={16} strokeWidth={2.4} />
            <span>+ 新建任务</span>
          </span>
        )}
        <a className="app-account-link" href={canOpenAdmin ? "/admin" : "/login"}>
          <span className="app-account-avatar">{userInitial(user)}</span>
          <span>{canOpenAdmin ? `${user?.name || "账号"} / 后台` : user?.name || "账号"}</span>
          <Settings aria-hidden="true" size={14} />
        </a>
      </div>
    </header>
  );
}
