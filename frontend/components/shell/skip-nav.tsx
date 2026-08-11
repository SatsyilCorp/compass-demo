export function SkipNav() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:inline-flex focus:min-h-11 focus:items-center focus:rounded-md focus:bg-gov-primary focus:px-4 focus:text-sm focus:font-bold focus:text-white focus:shadow-elevated"
    >
      Skip to main content
    </a>
  );
}
