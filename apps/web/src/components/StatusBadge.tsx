import { Badge, Box } from '@razorpay/blade/components';

import type { Action } from '../api/types';
import { ACTION_META } from './actionMeta';

/** Status is never colour alone: every badge has a word and an icon. */
export function StatusBadge({ action, suffix }: { action: Action; suffix?: string }) {
  const { label, color, Icon } = ACTION_META[action];
  return (
    <Box display="inline-flex" alignItems="center" gap="spacing.2">
      <Icon aria-hidden="true" focusable="false" />
      <Badge color={color}>{suffix ? `${label} ${suffix}` : label}</Badge>
    </Box>
  );
}
