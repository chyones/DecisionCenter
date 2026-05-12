import { FolderOpen } from 'lucide-react';
import type { ScreenState } from '../tokens';

export interface PlaceholderScreenProps {
  title: string;
  state: ScreenState;
  body?: string;
}

export function PlaceholderScreen({ title, state, body }: PlaceholderScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <FolderOpen
        className="h-12 w-12 text-text-muted"
        aria-hidden="true"
      />
      <h2 className="mt-3 text-heading font-semibold text-text-primary">
        {title}
      </h2>
      {body ? (
        <p className="mt-2 max-w-[400px] text-body text-text-secondary">
          {body}
        </p>
      ) : null}
      <p className="mt-4 text-caption text-text-muted">State: {state}</p>
    </div>
  );
}
