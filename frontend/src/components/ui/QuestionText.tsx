import { Fragment, useMemo, type ReactNode } from 'react';
import MathText from './MathText';

/**
 * Renders question text that may contain a simple HTML table.
 *
 * Some imported questions (mostly Accounting, plus a couple in Chemistry and
 * Economics) carry literal `<table><tr><th>…` markup in `question_text`.
 * Nothing rendered HTML, so students saw the raw tags as text and the question
 * was unusable.
 *
 * This parses that markup into real React elements. Deliberately NOT
 * `dangerouslySetInnerHTML`: question text is admin-editable, so injecting it
 * as HTML would be a stored-XSS hole. Parsing to a fixed element set means the
 * worst a malformed question can do is render badly.
 *
 * Supported subset, matching what actually appears in the bank:
 *   <table> <tr> <th> <td> <b> <u> <i>
 * Anything else is left as text and passed through MathText, so a question
 * mixing prose, math and a table all render correctly.
 *
 * `<u>` matters more than it looks. Around 700 English questions say "choose
 * the option opposite in meaning to the underlined word" -- if the underline
 * does not render, the question cannot be answered except by guessing which
 * word was meant. See scripts/repair_underlines.py for where that markup
 * came from.
 *
 * Use this anywhere `question_text` is displayed. Options and explanations
 * have no table markup, so plain MathText remains correct for those.
 */

type Segment =
  | { type: 'text'; value: string }
  | { type: 'table'; rows: Cell[][] };

type Cell = { text: string; header: boolean };

const TABLE_RE = /<table[^>]*>([\s\S]*?)<\/table>/gi;
const ROW_RE = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
const CELL_RE = /<(th|td)[^>]*>([\s\S]*?)<\/\1>/gi;
const INLINE_RE = /<(b|u|i)>([\s\S]*?)<\/\1>/gi;

const INLINE_TAG = {
  b: 'strong',
  u: 'u',
  i: 'em',
} as const;

function parseRows(inner: string): Cell[][] {
  const rows: Cell[][] = [];
  ROW_RE.lastIndex = 0;
  let rowMatch: RegExpExecArray | null;
  while ((rowMatch = ROW_RE.exec(inner)) !== null) {
    const cells: Cell[] = [];
    CELL_RE.lastIndex = 0;
    let cellMatch: RegExpExecArray | null;
    while ((cellMatch = CELL_RE.exec(rowMatch[1])) !== null) {
      cells.push({ text: cellMatch[2].trim(), header: cellMatch[1].toLowerCase() === 'th' });
    }
    if (cells.length) rows.push(cells);
  }
  return rows;
}

function split(input: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  TABLE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = TABLE_RE.exec(input)) !== null) {
    if (match.index > last) segments.push({ type: 'text', value: input.slice(last, match.index) });
    const rows = parseRows(match[1]);
    // A <table> we can't parse into rows falls back to text rather than
    // vanishing -- a visibly odd question beats a silently missing one.
    segments.push(rows.length ? { type: 'table', rows } : { type: 'text', value: match[0] });
    last = TABLE_RE.lastIndex;
  }
  if (last < input.length) segments.push({ type: 'text', value: input.slice(last) });
  return segments.length ? segments : [{ type: 'text', value: input }];
}

/**
 * Renders inline markup: <b>/<u>/<i> become real elements, everything around
 * them goes through MathText. Used for prose and for table cells alike.
 *
 * Still not `dangerouslySetInnerHTML` -- a fixed element set means the worst a
 * malformed or malicious question can do is render badly.
 */
function inlineContent(text: string): ReactNode {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  INLINE_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) out.push(<MathText key={`t${i}`} text={text.slice(last, m.index)} />);
    const Tag = INLINE_TAG[m[1].toLowerCase() as keyof typeof INLINE_TAG];
    out.push(
      <Tag key={`m${i}`}>
        <MathText text={m[2]} />
      </Tag>
    );
    last = INLINE_RE.lastIndex;
    i++;
  }
  if (last < text.length) out.push(<MathText key={`t${i}`} text={text.slice(last)} />);
  return out.length ? out : null;
}

/** True if the text carries inline markup we should parse rather than print. */
function hasInline(text: string): boolean {
  INLINE_RE.lastIndex = 0;
  return INLINE_RE.test(text);
}

export default function QuestionText({ text, className }: { text?: string | null; className?: string }) {
  const segments = useMemo(() => split(text || ''), [text]);
  const hasTable = segments.some((s) => s.type === 'table');

  // No table and no markup: behave exactly like MathText so existing layouts
  // are unchanged.
  if (!hasTable) {
    if (!hasInline(text || '')) return <MathText text={text} className={className} />;
    return <span className={className}>{inlineContent(text || '')}</span>;
  }

  return (
    <div className={className}>
      {segments.map((seg, i) => {
        if (seg.type === 'text') {
          if (!seg.value.trim()) return null;
          return (
            <span key={i} className="block mb-3">
              {inlineContent(seg.value)}
            </span>
          );
        }
        return (
          <div key={i} className="overflow-x-auto my-3 -mx-1">
            <table className="min-w-full text-sm border border-ink-200 rounded-lg overflow-hidden">
              <tbody>
                {seg.rows.map((row, r) => (
                  <tr key={r} className={r % 2 ? 'bg-ink-50/60' : 'bg-white'}>
                    {row.map((cell, c) => (
                      <Fragment key={c}>
                        {cell.header ? (
                          <th className="text-left font-semibold text-ink-900 px-3 py-2 border border-ink-200 bg-ink-100">
                            {inlineContent(cell.text)}
                          </th>
                        ) : (
                          <td className="text-ink-700 px-3 py-2 border border-ink-200 align-top">
                            {inlineContent(cell.text)}
                          </td>
                        )}
                      </Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
