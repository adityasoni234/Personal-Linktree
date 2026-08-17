/** Shared hooks. */

import { useCallback, useEffect, useRef, useState } from 'react';

export { useMutation, useQuery } from './useApi';
export type { MutationResult, QueryResult } from './useApi';

/** Debounce a rapidly-changing value (search boxes, live slug checks). */
export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  );
  useEffect(() => {
    const list = window.matchMedia(query);
    const listener = (event: MediaQueryListEvent) => setMatches(event.matches);
    setMatches(list.matches);
    list.addEventListener('change', listener);
    return () => list.removeEventListener('change', listener);
  }, [query]);
  return matches;
}

/** Copy to clipboard with a short-lived "copied" flag for the UI. */
export function useCopyToClipboard(resetAfter = 2000): {
  copied: boolean;
  copy: (value: string) => Promise<boolean>;
} {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const copy = useCallback(
    async (value: string) => {
      try {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => setCopied(false), resetAfter);
        return true;
      } catch {
        return false;
      }
    },
    [resetAfter],
  );

  return { copied, copy };
}

/** Close a popover when the user clicks outside it or presses Escape. */
export function useDismissable<T extends HTMLElement>(
  isOpen: boolean,
  onDismiss: () => void,
): React.RefObject<T> {
  const ref = useRef<T>(null);

  useEffect(() => {
    if (!isOpen) return;

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onDismiss();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onDismiss();
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, onDismiss]);

  return ref;
}

/** Set the document title, restoring the previous one on unmount. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} · IEEE SOU Link Hub` : 'IEEE SOU Link Hub';
    return () => {
      document.title = previous;
    };
  }, [title]);
}

/**
 * Keyboard-and-pointer list reordering.
 *
 * Uses the native HTML5 drag events for the mouse path, and exposes `moveItem`
 * so the same reorder is reachable with the keyboard — dragging alone is not
 * accessible.
 */
export function useReorder<T extends { id: string }>(
  items: T[],
  onReorder: (ordered: T[]) => void,
) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const move = useCallback(
    (fromIndex: number, toIndex: number) => {
      if (
        fromIndex === toIndex ||
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= items.length ||
        toIndex >= items.length
      ) {
        return;
      }
      const next = [...items];
      const [moved] = next.splice(fromIndex, 1);
      if (moved) next.splice(toIndex, 0, moved);
      onReorder(next);
    },
    [items, onReorder],
  );

  const moveItem = useCallback(
    (id: string, direction: -1 | 1) => {
      const index = items.findIndex((item) => item.id === id);
      move(index, index + direction);
    },
    [items, move],
  );

  const handlers = useCallback(
    (id: string) => ({
      draggable: true,
      onDragStart: (event: React.DragEvent) => {
        setDraggingId(id);
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', id);
      },
      onDragOver: (event: React.DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        if (overId !== id) setOverId(id);
      },
      onDrop: (event: React.DragEvent) => {
        event.preventDefault();
        const sourceId = event.dataTransfer.getData('text/plain') || draggingId;
        if (!sourceId || sourceId === id) return;
        move(
          items.findIndex((item) => item.id === sourceId),
          items.findIndex((item) => item.id === id),
        );
        setDraggingId(null);
        setOverId(null);
      },
      onDragEnd: () => {
        setDraggingId(null);
        setOverId(null);
      },
    }),
    [draggingId, overId, items, move],
  );

  return { draggingId, overId, handlers, moveItem };
}
