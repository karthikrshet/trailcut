import { Box, Heading, Spinner, Text } from '@razorpay/blade/components';
import { AnimatePresence, motion, useReducedMotionConfig } from 'motion/react';
import { LuCircleCheck, LuCircle } from 'react-icons/lu';

import type { Step } from '../state/useSession';

const STEPS: { id: Step; label: string }[] = [
  { id: 'reading', label: 'Reading statement' },
  { id: 'pricing', label: 'Checking expense ratios' },
  { id: 'planning', label: 'Planning your switch' },
];

/** Three honest steps that tick as the request progresses. */
export function ProcessingSteps({ step, kind }: { step: Step; kind: 'sample' | 'upload' }) {
  const reduce = useReducedMotionConfig();
  const current = STEPS.findIndex((s) => s.id === step);
  return (
    <div role="status" aria-live="polite">
    <Box display="flex" flexDirection="column" gap="spacing.6">
      <Heading as="h2" size="medium">
        {kind === 'sample' ? 'Loading the sample portfolio' : 'Working on your statement'}
      </Heading>
      <ol className="plain-list">
        {STEPS.map((s, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <li key={s.id}>
            <Box display="flex" alignItems="center" gap="spacing.3" marginBottom="spacing.4">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={done ? 'done' : active ? 'active' : 'todo'}
                  initial={reduce ? false : { opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.2 }}
                  style={{ display: 'inline-flex' }}
                >
                  {done ? (
                    <LuCircleCheck aria-hidden="true" />
                  ) : active ? (
                    <Spinner accessibilityLabel={s.label} size="medium" />
                  ) : (
                    <LuCircle aria-hidden="true" />
                  )}
                </motion.span>
              </AnimatePresence>
              <Text weight={active ? 'semibold' : 'regular'}>
                {s.label}
                {done ? <span className="sr-only"> (done)</span> : null}
              </Text>
            </Box>
            </li>
          );
        })}
      </ol>
      <Text color="surface.text.gray.muted" size="small">
        Your statement is processed in memory and never stored.
      </Text>
    </Box>
    </div>
  );
}
