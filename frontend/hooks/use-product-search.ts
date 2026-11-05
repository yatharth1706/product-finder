"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, createSearch, getSearch } from "@/lib/api";
import type { SearchJob } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export function useProductSearch() {
  const [searchId, setSearchId] = useState<string | null>(null);
  const [job, setJob] = useState<SearchJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const start = useCallback(async (amazonUrl: string) => {
    setSearchId(null);
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      const created = await createSearch(amazonUrl);
      if (isFinished(created)) {
        setJob(created);
      } else {
        setSearchId(created.search_id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }, []);

  useEffect(() => {
    if (!searchId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const latest = await getSearch(searchId);
        if (stopped) return;
        setJob(latest);
        if (isFinished(latest)) return;
      } catch (err) {
        if (stopped) return;
        setError(err instanceof ApiError ? err.message : "Lost contact with the server");
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [searchId]);

  const running = submitting || (searchId !== null && !error && !(job && isFinished(job)));

  return { job, error, running, start };
}

function isFinished(job: SearchJob) {
  return job.status === "completed" || job.status === "failed";
}
