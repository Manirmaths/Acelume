/**
 * The Acelume mark: a rounded indigo square containing a stylised "A".
 *
 * Kept as a component rather than an <img> so it stays crisp at any size, has
 * no network request, and can sit inline next to the wordmark. The same
 * geometry is mirrored in `public/favicon.svg` and the PWA icons under
 * `public/icons/` -- if you change one, regenerate the others (see
 * `tools/generate_icons.py`) so the browser tab, installed PWA, and in-app
 * header don't drift apart.
 */
export default function Logo({ className = 'w-8 h-8' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 512 512"
      className={className}
      role="img"
      aria-label="Acelume"
      focusable="false"
    >
      <defs>
        {/* id is namespaced -- multiple Logos can render on one page */}
        <linearGradient id="acelume-mark-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4f46e5" />
          <stop offset="1" stopColor="#3b32c9" />
        </linearGradient>
      </defs>
      <rect x="24" y="24" width="464" height="464" rx="124" fill="url(#acelume-mark-bg)" />
      <rect x="80" y="80" width="352" height="352" rx="96" fill="#ffffff" fillOpacity="0.07" />
      <g fill="none" stroke="#ffffff" strokeWidth="34">
        <path d="M181 372 V255 a75 75 0 0 1 150 0 V372" />
        <path d="M181 310 H331" />
      </g>
    </svg>
  );
}
