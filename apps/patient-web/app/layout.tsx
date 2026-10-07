import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/lib/session-context";

export const metadata: Metadata = {
  title: "CareFlow",
  description: "CareFlow patient assistant (portfolio demonstration, not a medical product).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
