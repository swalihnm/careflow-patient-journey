"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRole } from "@/lib/role-context";
import type { Role } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/worklist", label: "Worklist" },
  { href: "/escalations", label: "Escalations" },
  { href: "/experiments", label: "Experiments" },
  { href: "/claims", label: "Claims" },
  { href: "/quality", label: "Quality" },
  { href: "/audit", label: "Audit" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { role, setRole, selectableRoles } = useRole();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        Care<span>Flow</span>
      </div>
      <nav>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={pathname?.startsWith(item.href) ? "active" : ""}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="role-switcher">
        <label htmlFor="role-select">Viewing as</label>
        <select
          id="role-select"
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
        >
          {selectableRoles.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>
    </aside>
  );
}
