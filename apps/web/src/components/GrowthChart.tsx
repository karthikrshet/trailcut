import { Box, Text, useTheme } from '@razorpay/blade/components';
import { motion, useReducedMotionConfig } from 'motion/react';
import { useState } from 'react';

import type { GrowthPoint } from '../api/types';
import { formatINR } from '../lib/format';
import { pageIsVisible } from '../lib/visibility';

// Wide aspect so the chart stays a readable height on large screens.
const W = 960;
const H = 300;
const PAD = { top: 16, right: 8, bottom: 32, left: 8 };
const TICKS = [0, 5, 10, 15, 20];

function Swatch({ color, dashed }: { color: string; dashed?: boolean }) {
  return (
    <svg width="28" height="10" aria-hidden="true">
      <line x1="0" x2="28" y1="5" y2="5" stroke={color} strokeWidth="3" strokeDasharray={dashed ? '6 4' : undefined} />
    </svg>
  );
}

/**
 * Regular vs Direct value over 20 years; the shaded gap is money lost to
 * commission. Drawn from API figures only; positions are presentational.
 */
export function GrowthChart({ points }: { points: GrowthPoint[] }) {
  const { theme } = useTheme();
  const reduce = useReducedMotionConfig();
  // Animate only when on screen; hidden pages pause frames and would show empty lines.
  const [animated] = useState(() => !reduce && pageIsVisible());
  if (points.length < 2) return null;
  const regular = points.map((p) => Number(p.regular));
  const direct = points.map((p) => Number(p.direct));
  const max = Math.max(...direct, ...regular, 1);
  const lastYear = points[points.length - 1]?.year ?? 20;
  const x = (year: number) => PAD.left + (year / lastYear) * (W - PAD.left - PAD.right);
  const y = (v: number) => H - PAD.bottom - (v / max) * (H - PAD.top - PAD.bottom);
  const line = (vals: number[]) =>
    vals.map((v, i) => `${i ? 'L' : 'M'}${String(x(points[i]?.year ?? 0))},${String(y(v))}`).join(' ');
  const back = [...regular]
    .reverse()
    .map((v, i) => `L${String(x(points[points.length - 1 - i]?.year ?? 0))},${String(y(v))}`)
    .join(' ');
  const gap = `${line(direct)} ${back} Z`;
  const colors = theme.colors;
  const directColor = colors.interactive.background.positive.default;
  const regularColor = colors.interactive.icon.gray.muted;
  const last = points[points.length - 1];
  const fade = { initial: animated ? { opacity: 0 } : false, animate: { opacity: 1 } } as const;

  return (
    <Box display="flex" flexDirection="column" gap="spacing.3">
      <svg
        viewBox={`0 0 ${String(W)} ${String(H)}`}
        width="100%"
        style={{ maxHeight: '22rem' }}
        role="img"
        aria-label={
          last
            ? `After ${String(last.year)} years: ${formatINR(last.direct)} in Direct versus ${formatINR(last.regular)} in Regular.`
            : 'Growth chart'
        }
      >
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={H - PAD.bottom}
          y2={H - PAD.bottom}
          stroke={colors.surface.border.gray.muted}
        />
        <motion.path
          d={gap}
          fill={colors.feedback.background.negative.subtle}
          {...fade}
          transition={{ delay: animated ? 0.8 : 0, duration: animated ? 0.3 : 0 }}
        />
        {/* Regular stays dashed, as the legend says: it fades in rather than drawing. */}
        <motion.path
          d={line(regular)}
          fill="none"
          stroke={regularColor}
          strokeWidth={3}
          strokeDasharray="8 6"
          {...fade}
          transition={{ duration: animated ? 0.5 : 0 }}
        />
        {animated ? (
          <motion.path
            d={line(direct)}
            fill="none"
            stroke={directColor}
            strokeWidth={3}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.8 }}
          />
        ) : (
          <path d={line(direct)} fill="none" stroke={directColor} strokeWidth={3} />
        )}
        {TICKS.filter((t) => t <= lastYear).map((t, i, all) => (
          <text
            key={t}
            x={x(t)}
            y={H - 10}
            textAnchor={i === 0 ? 'start' : i === all.length - 1 ? 'end' : 'middle'}
            fontSize="13"
            fontFamily={theme.typography.fonts.family.text}
            fill={colors.surface.text.gray.muted}
          >
            {t === 0 ? 'Today' : `${String(t)} years`}
          </text>
        ))}
      </svg>
      <Box display="flex" gap="spacing.5" flexWrap="wrap" alignItems="center">
        <Box display="flex" alignItems="center" gap="spacing.2">
          <Swatch color={directColor} />
          <Text size="small">Direct plan (lower fees)</Text>
        </Box>
        <Box display="flex" alignItems="center" gap="spacing.2">
          <Swatch color={regularColor} dashed />
          <Text size="small">Regular plan (with commission)</Text>
        </Box>
        <Text size="small" color="surface.text.gray.muted">
          Shaded: money lost to commission
        </Text>
      </Box>
    </Box>
  );
}
