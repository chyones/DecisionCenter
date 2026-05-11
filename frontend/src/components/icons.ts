import {
  Ban,
  CheckCircle2,
  CircleDashed,
  Clock,
  Loader2,
  Lock,
  Plug,
  PlugZap,
  ShieldCheck,
  Stamp,
  TriangleAlert,
  Unplug,
  X,
  XCircle,
  type LucideIcon,
} from 'lucide-react';

import {
  STATUS_REGISTRY,
  type StatusIconName,
  type StatusValue,
} from '../tokens';

export const statusIconMap = {
  'shield-check': ShieldCheck,
  loader: Loader2,
  'circle-check': CheckCircle2,
  'triangle-alert': TriangleAlert,
  'x-circle': XCircle,
  clock: Clock,
  stamp: Stamp,
  ban: Ban,
  lock: Lock,
  plug: Plug,
  'plug-zap': PlugZap,
  unplug: Unplug,
  'circle-dashed': CircleDashed,
} as const satisfies Record<StatusIconName, LucideIcon>;

export function getStatusIcon(status: StatusValue): LucideIcon {
  return statusIconMap[STATUS_REGISTRY[status].icon];
}

export const closeIcon = X;
export const loadingIcon = Loader2;
export const warningIcon = TriangleAlert;
