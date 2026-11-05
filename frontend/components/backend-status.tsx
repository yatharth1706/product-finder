"use client";

import { Badge } from "@/components/ui/badge";
import { useBackendHealth } from "@/hooks/use-backend-health";

export function BackendStatus() {
  const { data, isPending, isError } = useBackendHealth();

  if (isPending) return <Badge variant="outline">Checking backend…</Badge>;
  if (isError || data?.status !== "healthy") {
    return <Badge variant="destructive">Backend unavailable</Badge>;
  }
  return <Badge className="bg-emerald-600 text-white">Backend healthy</Badge>;
}
