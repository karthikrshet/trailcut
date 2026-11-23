import { createContext, useContext } from 'react';

export type Scheme = 'light' | 'dark';
export type ThemeState = { scheme: Scheme; setScheme: (s: Scheme) => void };

export const ThemeContext = createContext<ThemeState>({ scheme: 'light', setScheme: () => undefined });

/** Current colour scheme and a setter (light/dark). */
export function useColorScheme(): ThemeState {
  return useContext(ThemeContext);
}
