import type { Metadata } from "next";
import "./globals.css";
import { RoleProvider } from "@/lib/role-context";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "CareFlow — Care Team",
  description: "CareFlow care-team dashboard (portfolio demonstration, not a medical product).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <RoleProvider>
          <div className="app-shell">
            <Sidebar />
            <main className="main">{children}</main>
          </div>
        </RoleProvider>
      </body>
    </html>
  );
}
