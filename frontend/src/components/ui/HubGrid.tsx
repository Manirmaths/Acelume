import { Link } from 'react-router-dom';

export interface HubLink {
  to: string;
  icon: string;
  title: string;
  description: string;
  /** Optional right-hand badge, e.g. a count of items due. */
  badge?: string | number | null;
  /** Visually leads the group. Use for at most one link per hub. */
  primary?: boolean;
}

/**
 * The card grid used by the Practice / Progress / Profile hub pages.
 *
 * These hubs exist because the app previously exposed fourteen primary
 * navigation destinations. Fourteen equally-weighted choices is not a menu,
 * it is a search problem, and it pushed engagement features (leagues,
 * battles, blitz, achievements) into direct competition with the student's
 * actual learning work. Nesting them one level down under five destinations
 * keeps every feature reachable in two taps while making the top level
 * describe intent -- learn, practise, check progress -- rather than
 * inventory.
 */
export default function HubGrid({ links }: { links: HubLink[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {links.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className={`group flex items-start gap-4 rounded-2xl border p-4 transition-colors ${
            link.primary
              ? 'border-brand-200 bg-brand-50/60 hover:border-brand-400 hover:bg-brand-50'
              : 'border-ink-100 bg-white hover:border-brand-200 hover:bg-brand-50/40'
          }`}
        >
          <div
            className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${
              link.primary ? 'bg-brand-500 text-white' : 'bg-ink-100 text-ink-500 group-hover:text-brand-600'
            }`}
            aria-hidden="true"
          >
            <i className={link.icon} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="font-display font-bold text-ink-900 truncate">{link.title}</p>
              {link.badge != null && link.badge !== 0 && (
                <span className="flex-shrink-0 rounded-full bg-brand-500 text-white text-xs font-bold px-2 py-0.5">
                  {link.badge}
                </span>
              )}
            </div>
            <p className="text-sm text-ink-500 mt-0.5 leading-snug">{link.description}</p>
          </div>

          <i className="fa-solid fa-chevron-right text-ink-300 text-xs mt-3.5 flex-shrink-0 group-hover:text-brand-400" aria-hidden="true" />
        </Link>
      ))}
    </div>
  );
}
