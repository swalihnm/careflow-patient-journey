"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Role } from "./api";

const STORAGE_KEY = "careflow_role";
const SELECTABLE_ROLES: Role[] = ["clinician", "nurse", "admin", "auditor"];

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
  selectableRoles: Role[];
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({ children }: { children: React.ReactNode }) {
  const [role, setRoleState] = useState<Role>("clinician");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && SELECTABLE_ROLES.includes(stored as Role)) {
      setRoleState(stored as Role);
    }
  }, []);

  function setRole(next: Role) {
    setRoleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }

  return (
    <RoleContext.Provider value={{ role, setRole, selectableRoles: SELECTABLE_ROLES }}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (!ctx) {
    throw new Error("useRole must be used within a RoleProvider");
  }
  return ctx;
}
