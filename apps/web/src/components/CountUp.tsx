import { animate, useReducedMotionConfig } from 'motion/react';
import { useEffect, useState } from 'react';

import { formatINR, type FormatINROptions } from '../lib/format';

/**
 * Counts a rupee figure up from ₹0 once. The final text is always the exact
 * formatted value; with reduced motion it appears immediately.
 */
export function CountUp({
  value,
  options,
  durationMs = 900,
}: {
  value: string;
  options?: FormatINROptions;
  durationMs?: number;
}) {
  const reduce = useReducedMotionConfig();
  const compact = options?.compact ?? false;
  const paise = options?.paise ?? false;
  const final = formatINR(value, { compact, paise });
  const [text, setText] = useState(formatINR('0', { compact, paise }));

  useEffect(() => {
    if (reduce) return;
    // The animation only drives the visual tween; it ends on the exact string.
    const whole = value.split('.')[0] ?? '0';
    const target = Number(whole);
    const controls = animate(0, target, {
      duration: durationMs / 1000,
      ease: 'easeOut',
      onUpdate: (v) => {
        setText(formatINR(String(Math.round(v)), { compact, paise }));
      },
      onComplete: () => {
        setText(final);
      },
    });
    return () => {
      controls.stop();
    };
  }, [value, final, reduce, durationMs, compact, paise]);

  return (
    <span aria-label={final}>
      <span aria-hidden="true">{reduce ? final : text}</span>
    </span>
  );
}
