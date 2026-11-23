import { BladeProvider, Box, Switch, Text, useTheme } from '@razorpay/blade/components';
import { bladeTheme } from '@razorpay/blade/tokens';
import { MotionConfig } from 'motion/react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { LuMoon, LuSun } from 'react-icons/lu';

import { type Scheme, ThemeContext, type ThemeState, useColorScheme } from './themeContext';

const KEY = 'trailcut.colorScheme';

function initialScheme(): Scheme {
  try {
    const saved = window.localStorage.getItem(KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    // Storage blocked (private mode): fall back to the system setting.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}


/** BladeProvider reads colorScheme only on mount; later changes go through its setter. */
function SchemeSync({ scheme }: { scheme: Scheme }) {
  const { setColorScheme } = useTheme();
  useEffect(() => {
    setColorScheme(scheme);
  }, [scheme, setColorScheme]);
  return null;
}

/** Blade theme + reduced-motion handling for the whole app, with a light/dark switch. */
export function ThemeRoot({ children }: { children: ReactNode }) {
  const [scheme, setSchemeState] = useState<Scheme>(initialScheme);
  useEffect(() => {
    document.documentElement.style.colorScheme = scheme;
  }, [scheme]);
  const value = useMemo<ThemeState>(
    () => ({
      scheme,
      setScheme: (s) => {
        setSchemeState(s);
        try {
          window.localStorage.setItem(KEY, s);
        } catch {
          // Not saved; the choice still applies for this visit.
        }
      },
    }),
    [scheme],
  );
  return (
    <ThemeContext.Provider value={value}>
      <BladeProvider themeTokens={bladeTheme} colorScheme={scheme}>
        <SchemeSync scheme={scheme} />
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </BladeProvider>
    </ThemeContext.Provider>
  );
}


export function ThemeToggle() {
  const { scheme, setScheme } = useColorScheme();
  const dark = scheme === 'dark';
  return (
    <Box display="flex" alignItems="center" gap="spacing.2">
      {dark ? <LuMoon aria-hidden="true" /> : <LuSun aria-hidden="true" />}
      <Text size="small" color="surface.text.gray.muted">
        Dark
      </Text>
      <Switch
        size="small"
        accessibilityLabel="Dark mode"
        isChecked={dark}
        onChange={({ isChecked }) => {
          setScheme(isChecked ? 'dark' : 'light');
        }}
      />
    </Box>
  );
}
