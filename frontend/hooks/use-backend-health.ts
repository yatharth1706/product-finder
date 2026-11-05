"use client";

import { useQuery } from "@tanstack/react-query";

import { getHealth } from "@/lib/api";

export function useBackendHealth() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30_000 });
}
