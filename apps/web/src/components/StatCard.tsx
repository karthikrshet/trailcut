import { Box, Card, CardBody, Heading, Text } from '@razorpay/blade/components';
import { motion, useReducedMotionConfig } from 'motion/react';
import type { ReactNode } from 'react';
import type { IconType } from 'react-icons';

export function StatCard({
  label,
  value,
  hint,
  Icon,
  index = 0,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  Icon: IconType;
  index?: number;
}) {
  const reduce = useReducedMotionConfig();
  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: 'easeOut', delay: reduce ? 0 : index * 0.06 }}
      style={{ height: '100%' }}
    >
      <Card padding="spacing.5" height="100%">
        <CardBody>
          <Box display="flex" flexDirection="column" gap="spacing.2">
            <Box display="flex" alignItems="center" gap="spacing.2">
              <Icon aria-hidden="true" />
              <Text size="small" color="surface.text.gray.muted">
                {label}
              </Text>
            </Box>
            <Heading as="span" size="large">
              {value}
            </Heading>
            {hint ? (
              <Text size="small" color="surface.text.gray.muted">
                {hint}
              </Text>
            ) : null}
          </Box>
        </CardBody>
      </Card>
    </motion.div>
  );
}
