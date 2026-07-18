"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/chat" : "/login");
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-slate-400">Loading OmniMind AI…</p>
    </main>
  );
}
