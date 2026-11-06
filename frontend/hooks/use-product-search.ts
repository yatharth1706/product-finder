"use client";

import { useCallback, useState } from "react";
import { ApiError, streamSearch } from "@/lib/api";
import type { MarketplaceResult, Platform, Product } from "@/lib/types";

export interface SearchState {
  product: Product | null;
  /** Marketplaces being searched, known as soon as the product is. */
  platforms: Platform[];
  results: Partial<Record<Platform, MarketplaceResult>>;
  error: string | null;
  running: boolean;
}

const EMPTY: SearchState = {
  product: null,
  platforms: [],
  results: {},
  error: null,
  running: false,
};

export function useProductSearch() {
  const [state, setState] = useState<SearchState>(EMPTY);

  const start = useCallback(async (amazonUrl: string) => {
    setState({ ...EMPTY, running: true });
    try {
      await streamSearch(amazonUrl, (event) => {
        setState((current) => {
          switch (event.type) {
            case "product":
              return { ...current, product: event.product, platforms: event.platforms ?? [] };
            case "result":
              if (!event.result) return current;
              return {
                ...current,
                results: { ...current.results, [event.result.platform]: event.result },
              };
            case "failed":
              return { ...current, error: event.error, running: false };
            case "completed":
              return { ...current, running: false };
            default:
              return current;
          }
        });
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Lost contact with the server";
      setState((current) => ({ ...current, error: message }));
    } finally {
      setState((current) => ({ ...current, running: false }));
    }
  }, []);

  return { ...state, start };
}
