"use client";

import { ChevronDown, Plus } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { clearSession, getStoredUser } from "@/lib/session";
import type { User } from "@/lib/api";

const navItems = [
  { href: "/", label: "工作台" },
  { href: "/rules", label: "规则配置" },
  { href: "/reports", label: "检查档案" }
];

type RulesActionsState = {
  canPublish: boolean;
  isPublishing: boolean;
};

function isActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(href);
}

function userInitial(user: User | null) {
  return (user?.name || user?.uid || "账").slice(0, 1);
}

const permissionLabels: Record<string, string> = {
  inspection_engineer: "点检执行",
  rules_admin: "规则管理",
  project_admin: "项目管理",
  super_admin: "权限管理"
};

function permissionSummary(user: User | null) {
  if (!user?.permissions.length) {
    return "未分配权限";
  }
  return user.permissions.map((permission) => permissionLabels[permission] || permission).join(" / ");
}

export function AppNav() {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const [rulesActionsState, setRulesActionsState] = useState<RulesActionsState>({
    canPublish: false,
    isPublishing: false
  });
  const accountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function syncStoredUser() {
      setUser(getStoredUser());
    }
    syncStoredUser();
    window.addEventListener("checkflow:session-changed", syncStoredUser);
    return () => window.removeEventListener("checkflow:session-changed", syncStoredUser);
  }, []);

  useEffect(() => {
    if (!isAccountMenuOpen) {
      return;
    }

    function closeOnOutsideClick(event: MouseEvent) {
      if (!accountRef.current?.contains(event.target as Node)) {
        setIsAccountMenuOpen(false);
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsAccountMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isAccountMenuOpen]);

  useEffect(() => {
    function syncRulesActionsState(event: Event) {
      const detail = (event as CustomEvent<RulesActionsState>).detail;
      if (!detail) {
        return;
      }
      setRulesActionsState({
        canPublish: Boolean(detail.canPublish),
        isPublishing: Boolean(detail.isPublishing)
      });
    }

    window.addEventListener("checkflow:rules-actions-state", syncRulesActionsState);
    return () => window.removeEventListener("checkflow:rules-actions-state", syncRulesActionsState);
  }, []);

  const isHome = pathname === "/";
  const isRules = pathname.startsWith("/rules");
  const canCreateTask = Boolean(user?.permissions.includes("inspection_engineer"));

  function openNewTaskModal() {
    window.dispatchEvent(new CustomEvent("checkflow:new-task"));
  }

  function openRulesHistory() {
    window.dispatchEvent(new CustomEvent("checkflow:rules-open-history"));
  }

  function openRulesPublish() {
    window.dispatchEvent(new CustomEvent("checkflow:rules-open-publish"));
  }

  function toggleAccountMenu() {
    if (!user) {
      window.location.href = "/login";
      return;
    }
    setIsAccountMenuOpen((current) => !current);
  }

  function openAdmin() {
    setIsAccountMenuOpen(false);
    window.location.href = "/admin";
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setIsAccountMenuOpen(false);
    window.location.href = "/login";
  }

  return (
    <header className="app-topbar">
      <a className="app-brand" href="/" aria-label="CheckFlow 工作台">
        <span className="app-logo">✓</span>
        <span className="app-brand-text">CheckFlow</span>
      </a>
      <nav className="app-nav" aria-label="主导航">
        {navItems.map((item) => (
          <a className={isActive(pathname, item.href) ? "active" : ""} href={item.href} key={item.href}>
            <span>{item.label}</span>
          </a>
        ))}
      </nav>
      <div className="app-topbar-actions">
        {isHome ? (
          canCreateTask ? (
            <button className="app-topbar-button app-topbar-button-primary app-create-task" type="button" onClick={openNewTaskModal}>
              <Plus aria-hidden="true" size={15} strokeWidth={2.4} />
              <span>+ 新建任务</span>
            </button>
          ) : (
            <span className="app-topbar-button app-topbar-button-primary app-create-task disabled" title="当前账号没有点检执行权限" aria-disabled="true">
              <Plus aria-hidden="true" size={15} strokeWidth={2.4} />
              <span>+ 新建任务</span>
            </span>
          )
        ) : null}
        {isRules ? (
          <>
            <button className="app-topbar-button app-topbar-button-secondary" type="button" onClick={openRulesHistory}>
              版本历史
            </button>
            <button
              className="app-topbar-button app-topbar-button-primary"
              type="button"
              disabled={!rulesActionsState.canPublish || rulesActionsState.isPublishing}
              onClick={openRulesPublish}
            >
              {rulesActionsState.isPublishing ? "发布中..." : "发布规则版本"}
            </button>
          </>
        ) : null}
        <div className="app-account" ref={accountRef}>
          <button
            className="app-account-link"
            type="button"
            onClick={toggleAccountMenu}
            aria-haspopup={user ? "menu" : undefined}
            aria-expanded={user ? isAccountMenuOpen : undefined}
          >
            <span className="app-account-avatar">{userInitial(user)}</span>
            <span>{user?.name || "账号"}</span>
            {user ? <ChevronDown aria-hidden="true" className="app-account-caret" size={14} /> : null}
          </button>
          {user && isAccountMenuOpen ? (
            <div className="app-account-menu" role="menu" aria-label="账号菜单">
              <div className="app-account-menu-head">
                <div className="app-account-menu-label">当前用户信息</div>
                <div className="app-account-menu-name">{user.name}</div>
                <div className="app-account-menu-meta">{user.uid}</div>
                <div className="app-account-menu-role">{permissionSummary(user)}</div>
              </div>
              <button className="app-account-menu-item" type="button" role="menuitem" onClick={openAdmin}>
                后台管理
              </button>
              <div className="app-account-menu-divider" />
              <button className="app-account-menu-item danger" type="button" role="menuitem" onClick={handleLogout}>
                退出登录
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
