import { useEffect } from 'react';

const SITE_NAME = 'Acelume';
const DEFAULT_TITLE = 'Acelume — Exam Preparation and University Learning';

/**
 * Sets the document title (and, optionally, the meta description) for the
 * current page. Deliberately not a dependency (react-helmet-async etc.) --
 * this SPA has no SSR/prerendering, so a full metadata library would add
 * weight without helping crawlers that don't execute JS anyway; this covers
 * the two things that actually matter for a client-rendered app: the
 * browser tab title (every visit) and the description tag for crawlers that
 * *do* run JS (Googlebot does).
 *
 * `index.html` still carries static defaults for crawlers/link-preview bots
 * that never execute JS at all -- this hook only overrides them after
 * hydration, for real browser navigations.
 */
export default function useDocumentMeta(title: string, description?: string) {
  useEffect(() => {
    const fullTitle = title ? `${title} | ${SITE_NAME}` : DEFAULT_TITLE;
    const prevTitle = document.title;
    document.title = fullTitle;

    let descTag: HTMLMetaElement | null = null;
    let prevDescription: string | null = null;
    if (description) {
      descTag = document.querySelector('meta[name="description"]');
      if (descTag) {
        prevDescription = descTag.getAttribute('content');
        descTag.setAttribute('content', description);
      }
    }

    return () => {
      document.title = prevTitle;
      if (descTag && prevDescription !== null) {
        descTag.setAttribute('content', prevDescription);
      }
    };
  }, [title, description]);
}
