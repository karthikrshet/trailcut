import { animate, useReducedMotionConfig } from 'motion/react';
import { useEffect, useState } from 'react';

import { formatINR, type FormatINROptions } from '../lib/format';
import { pageIsVisible } from '../lib/visibility';

/**
 * Counts a rupee figure up from ₹0 once. The final text is always the exact
 * formatted value. With reduced motion, or when the page isn't visible (a
 * background tab, a preview or a crawler pauses animation frames), the final
 * value shows immediately instead of a stalled ₹0.
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
  const [animated] = useState(() => !reduce && pageIsVisible());
  const [text, setText] = useState(animated ? formatINR('0', { compact, paise }) : final);

  useEffect(() => {
    if (!animated) return;
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
      setText(final);
    };
  }, [value, final, animated, durationMs, compact, paise]);

  return (
    <span aria-label={final}>
      <span aria-hidden="true">{animated && !reduce ? text : final}</span>
    </span>
  );
}
