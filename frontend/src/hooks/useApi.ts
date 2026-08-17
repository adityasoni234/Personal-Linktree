/**
 * Minimal data-fetching hooks.
 *
 * The app does not need a full query cache, so rather than pulling in another
 * dependency these cover the two shapes actually used: "load this on mount" and
 * "run this on demand".
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '@/api/client';

interface QueryState<T> {
  data: T | null;
  error: ApiError | null;
  isLoading: boolean;
  /** True while refetching with data already on screen (no skeleton flash). */
  isRefreshing: boolean;
}

export interface QueryResult<T> extends QueryState<T> {
  refetch: () => Promise<void>;
  setData: (updater: T | ((current: T | null) => T | null)) => void;
}

export function useQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { enabled?: boolean } = {},
): QueryResult<T> {
  const enabled = options.enabled ?? true;
  const [state, setState] = useState<QueryState<T>>({
    data: null,
    error: null,
    isLoading: enabled,
    isRefreshing: false,
  });

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  // Guards against a slow earlier request overwriting a newer result.
  const requestId = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async () => {
    const id = ++requestId.current;
    setState((previous) => ({
      ...previous,
      isLoading: previous.data === null,
      isRefreshing: previous.data !== null,
      error: null,
    }));

    try {
      const data = await fetcherRef.current();
      if (!mounted.current || id !== requestId.current) return;
      setState({ data, error: null, isLoading: false, isRefreshing: false });
    } catch (error) {
      if (!mounted.current || id !== requestId.current) return;
      setState((previous) => ({
        ...previous,
        error:
          error instanceof ApiError
            ? error
            : new ApiError(0, 'UNKNOWN', 'Something went wrong'),
        isLoading: false,
        isRefreshing: false,
      }));
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, isLoading: false, isRefreshing: false });
      return;
    }
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run, ...deps]);

  const setData = useCallback((updater: T | ((current: T | null) => T | null)) => {
    setState((previous) => ({
      ...previous,
      data:
        typeof updater === 'function'
          ? (updater as (current: T | null) => T | null)(previous.data)
          : updater,
    }));
  }, []);

  return { ...state, refetch: run, setData };
}

export interface MutationResult<TArgs extends unknown[], TResult> {
  mutate: (...args: TArgs) => Promise<TResult>;
  isPending: boolean;
  error: ApiError | null;
  reset: () => void;
}

export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): MutationResult<TArgs, TResult> {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const actionRef = useRef(action);
  actionRef.current = action;

  const mutate = useCallback(async (...args: TArgs) => {
    setIsPending(true);
    setError(null);
    try {
      return await actionRef.current(...args);
    } catch (caught) {
      const apiError =
        caught instanceof ApiError
          ? caught
          : new ApiError(0, 'UNKNOWN', 'Something went wrong');
      setError(apiError);
      throw apiError;
    } finally {
      setIsPending(false);
    }
  }, []);

  return { mutate, isPending, error, reset: () => setError(null) };
}
