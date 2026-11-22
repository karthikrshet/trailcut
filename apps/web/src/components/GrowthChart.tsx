import { Box, Text, useTheme } from '@razorpay/blade/components';
import { motion, useReducedMotionConfig } from 'motion/react';

import type { GrowthPoint } from '../api/types';
import { formatINR } from '../lib/format';

const W = 640;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 28, left: 16 };

/**
 * Regular vs Direct value over 20 years; the shaded gap is money lost to
 * commission. Drawn from API figures only; positions are presentational.
 */
export function GrowthChart({ points }: { points: GrowthPoint[] }) {
  const { theme } = useTheme();
  const reduce = useReducedMotionConfig();
  if (points.length < 2) return null;
  const regular = points.map((p) => Number(p.regular));
  const direct = points.map((p) => Number(p.direct));
  const max = Math.max(...direct, ...regular, 1);
  const lastYear = points[points.length - 1]?.year ?? 20;
  const x = (year: number) => PAD.left + (year / lastYear) * (W - PAD.left - PAD.right);
  const y = (v: number) => H - PAD.bottom - (v / max) * (H - PAD.top - PAD.bottom);
  const line = (vals: number[]) => vals.map((v, i) => `${i ? 'L' : 'M'}${String(x(points[i]?.year ?? 0))},${String(y(v))}`).join(' ');
  const gap = `${line(direct)} ${[...regular].reverse().map((v, i) => `L${String(x(points[points.length - 1 - i]?.year ?? 0))},${String(y(v))}`).join(' ')} Z`;
  const colors = theme.colors;
  const last = points[points.length - 1];
  const draw = reduce ? { pathLength: 1 } : { pathLength: [0, 1] };

  return (
    <Box display="flex" flexDirection="column" gap="spacing.3">
      <svg
        viewBox={`0 0 ${String(W)} ${String(H)}`}
        width="100%"
        role="img"
        aria-label={
          last
            ? `After ${String(last.year)} years: ${formatINR(last.direct)} in Direct versus ${formatINR(last.regular)} in Regular.`
            : 'Growth chart'
        }
      >
        <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} stroke={colors.surface.border.gray.muted} />
        <motion.path
          d={gap}
          fill={colors.feedback.background.negative.subtle}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: reduce ? 0 : 0.8, duration: reduce ? 0.2 : 0.3 }}
        />
        <motion.path d={line(direct)} fill="none" stroke={colors.interactive.background.positive.default} strokeWidth={3} animate={draw} transition={{ duration: reduce ? 0 : 0.8 }} />
        <motion.path d={line(regular)} fill="none" stroke={colors.interactive.icon.gray.muted} strokeWidth={3} strokeDasharray="6 4" animate={draw} transition={{ duration: reduce ? 0 : 0.8 }} />
        {[0, 5, 10, 15, 20].filter((t) => t <= lastYear).map((t) => (
          <text key={t} x={x(t)} y={H - 8} textAnchor="middle" fontSize="12" fill={colors.surface.text.gray.muted}>
            {t === 0 ? 'Today' : `${String(t)}y`}
          </text>
        ))}
      </svg>
      <Box display="flex" gap="spacing.5" flexWrap="wrap">
        <Text size="small">— Direct plan (lower fees)</Text>
        <Text size="small">- - Regular plan (with commission)</Text>
        <Text size="small">Shaded: money lost to commission</Text>
      </Box>
    </Box>
  );
}
