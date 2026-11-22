import { Box, Text } from '@razorpay/blade/components';
import { motion, useReducedMotionConfig } from 'motion/react';
import { LuCalendar } from 'react-icons/lu';

import type { TimelineStep } from '../api/types';
import { formatINR } from '../lib/format';

/** Switch dates in order, "Now" first. Scrolls sideways on small screens. */
export function Timeline({ steps }: { steps: TimelineStep[] }) {
  const reduce = useReducedMotionConfig();
  if (steps.length === 0) return null;
  return (
    <ol className="plain-list row-list" aria-label="Switch timeline">
      {steps.map((s, i) => (
        <motion.li
          key={s.on}
          initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.25, delay: reduce ? 0 : Math.min(i, 10) * 0.08 }}
          style={{ listStyle: 'none', flex: '0 0 auto' }}
        >
          <Box display="flex" flexDirection="column" gap="spacing.1" minWidth="112px">
            <Box display="flex" alignItems="center" gap="spacing.2">
              <LuCalendar aria-hidden="true" />
              <Text weight="semibold">{s.label}</Text>
            </Box>
            <Text size="small" color="surface.text.gray.muted">
              {`${String(s.lots)} ${s.lots === 1 ? 'lot' : 'lots'} · ${formatINR(s.value, { compact: true })}`}
            </Text>
          </Box>
        </motion.li>
      ))}
    </ol>
  );
}
