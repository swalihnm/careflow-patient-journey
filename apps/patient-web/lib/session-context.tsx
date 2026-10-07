"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Lang } from "./i18n";

const STORAGE_KEY = "careflow_patient_session";

interface StoredSession {
  patientId: string | null;
  lang: Lang;
  consented: boolean;
  threadId: string | null;
}

interface SessionContextValue extends StoredSession {
  setPatientId: (id: string) => void;
  setLang: (lang: Lang) => void;
  setConsented: (v: boolean) => void;
  setThreadId: (id: string) => void;
  ready: boolean;
}

const defaultSession: StoredSession = { patientId: null, lang: "en", consented: false, threadId: null };

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StoredSession>(defaultSession);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setSession({ ...defaultSession, ...JSON.parse(stored) });
      }
    } catch {
      // ignore -- a corrupted/blocked localStorage just means a fresh session
    }
    setReady(true);
  }, []);

  function persist(next: StoredSession) {
    setSession(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // per-viewer convenience only -- fine if this silently doesn't persist
    }
  }

  const value: SessionContextValue = {
    ...session,
    ready,
    setPatientId: (id) => persist({ ...session, patientId: id, threadId: null }),
    setLang: (lang) => persist({ ...session, lang }),
    setConsented: (v) => persist({ ...session, consented: v }),
    setThreadId: (id) => persist({ ...session, threadId: id }),
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}
