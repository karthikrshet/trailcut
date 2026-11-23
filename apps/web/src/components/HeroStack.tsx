import { Box, Card, CardBody, Text } from '@razorpay/blade/components';
import { motion, useMotionValue, useReducedMotionConfig, useSpring, useTransform } from 'motion/react';
import type { PointerEvent } from 'react';

import type { Action } from '../api/types';
import { StatusBadge } from './StatusBadge';

const CARDS: { fund: string; action: Action; suffix?: string; why: string }[] = [
  { fund: 'Flexi Cap Fund', action: 'switch_now', why: 'No tax and no exit load today.' },
  { fund: 'Small Cap Fund', action: 'wait', suffix: 'until it turns long term', why: 'The gain is taxed less after 12 months.' },
  { fund: 'Corporate Bond Fund', action: 'keep', why: 'Switching costs more than it saves.' },
];

/**
 * A 3D stack of example plan cards for the landing page. Tilts toward the
 * pointer; static with reduced motion. Illustrative only: no figures.
 */
export function HeroStack() {
  const reduce = useReducedMotionConfig();
  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-28, -12]), { stiffness: 120, damping: 18 });
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [22, 10]), { stiffness: 120, damping: 18 });

  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width - 0.5);
    py.set((e.clientY - r.top) / r.height - 0.5);
  };
  const onLeave = () => {
    px.set(0);
    py.set(0);
  };

  return (
    <div
      aria-hidden="true"
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{ perspective: '1100px', paddingBlock: '1.5rem' }}
    >
      <motion.div
        style={{
          transformStyle: 'preserve-3d',
          rotateX: reduce ? 16 : rotateX,
          rotateY: reduce ? -20 : rotateY,
          display: 'grid',
          gap: '0.75rem',
          maxWidth: '26rem',
        }}
      >
        {CARDS.map((c, i) => (
          <motion.div
            key={c.fund}
            initial={reduce ? false : { opacity: 0, z: -80 }}
            animate={{ opacity: 1, z: (CARDS.length - i) * 22 }}
            transition={{ duration: 0.5, delay: reduce ? 0 : 0.2 + i * 0.12, ease: 'easeOut' }}
            style={{ transformStyle: 'preserve-3d' }}
          >
            <Card padding="spacing.5">
              <CardBody>
                <Box display="flex" flexDirection="column" gap="spacing.2">
                  <Box display="flex" justifyContent="space-between" alignItems="center" gap="spacing.3">
                    <Text weight="semibold">{c.fund}</Text>
                    <StatusBadge action={c.action} {...(c.suffix ? { suffix: c.suffix } : {})} />
                  </Box>
                  <Text size="small" color="surface.text.gray.muted">
                    {c.why}
                  </Text>
                </Box>
              </CardBody>
            </Card>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
