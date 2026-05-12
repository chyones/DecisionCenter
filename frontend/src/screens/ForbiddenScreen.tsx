import { useEffect, useState } from 'react';
import { Ban } from 'lucide-react';
import { useRole } from '../routing/RoleContext';
import { getDefaultLanding } from '../routing/guards';

export function ForbiddenScreen() {
  const { role } = useRole();
  const [countdown, setCountdown] = useState(5);

  useEffect(() => {
    if (countdown <= 0) {
      window.location.hash = getDefaultLanding(role);
      return;
    }
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown, role]);

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Ban className="h-12 w-12 text-error" aria-hidden="true" />
      <h2 className="mt-3 text-heading font-semibold text-text-primary">
        Access denied
      </h2>
      <p className="mt-2 max-w-[400px] text-body text-text-secondary">
        You do not have permission to view this page.
      </p>
      <p className="mt-1 text-caption text-text-muted">
        Your role: {role}.
      </p>
      <p className="mt-4 text-caption text-text-muted">
        Redirecting to your default landing in {countdown}s…
      </p>
    </div>
  );
}
