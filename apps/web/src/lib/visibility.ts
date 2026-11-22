/**
 * True when the page is on screen. Hidden pages (background tabs, prerender,
 * some preview and screenshot tools) pause animation frames, so entrance
 * animations should show their final state there instead.
 */
export function pageIsVisible(): boolean {
  return typeof document !== 'undefined' && document.visibilityState === 'visible';
}
