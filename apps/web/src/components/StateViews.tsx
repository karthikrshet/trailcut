import { Alert, Box, Button, Skeleton, Text } from '@razorpay/blade/components';
import type { ReactNode } from 'react';

/** Loading placeholder that keeps the layout from jumping. */
export function LoadingBlock({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" aria-label={label}>
    <Box display="flex" flexDirection="column" gap="spacing.4">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} height="56px" width="100%" borderRadius="medium" />
      ))}
    </Box>
    </div>
  );
}

/** Plain-language error with one clear next action. */
export function ErrorBlock({
  title,
  message,
  actionLabel,
  onAction,
}: {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <Box display="flex" flexDirection="column" gap="spacing.4">
      <Alert title={title} description={message} color="negative" isDismissible={false} isFullWidth />
      {actionLabel && onAction ? (
        <Box>
          <Button variant="secondary" onClick={onAction}>
            {actionLabel}
          </Button>
        </Box>
      ) : null}
    </Box>
  );
}

/** Friendly empty state. */
export function EmptyBlock({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Box display="flex" flexDirection="column" gap="spacing.2" padding="spacing.6" textAlign="center">
      <Text weight="semibold">{title}</Text>
      {children ? <Text color="surface.text.gray.muted">{children}</Text> : null}
    </Box>
  );
}
