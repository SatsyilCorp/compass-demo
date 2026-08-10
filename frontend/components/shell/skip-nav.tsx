/**
 * Skip-to-main-content link. Hidden until focused; first Tab stop on every
 * page (WCAG 2.4.1 bypass blocks).
 */
export function SkipNav() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-md focus:bg-gov-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-elevated"
    >
      Skip to main content
    </a>
  );
}
