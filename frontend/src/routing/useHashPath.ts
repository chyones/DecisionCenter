import { useState, useEffect } from 'react';

function readHashPath(): string {
  return window.location.hash.replace(/^#/, '') || '/';
}

/**
 * React hook that tracks the current hash-based path.
 * Any component can use this to react to route changes without prop-drilling.
 */
export function useHashPath(): string {
  const [path, setPath] = useState(readHashPath);

  useEffect(() => {
    const handler = () => setPath(readHashPath());
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  return path;
}
