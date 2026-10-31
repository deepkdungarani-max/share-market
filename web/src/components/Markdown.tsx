import React from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Tailwind has no prose styles here, so every element the teacher writes gets its own classes.
const components: Components = {
  h1: ({ children }) => <h3 className="mb-2 mt-5 text-lg font-semibold text-ink first:mt-0">{children}</h3>,
  h2: ({ children }) => <h4 className="mb-2 mt-5 text-base font-semibold text-ink first:mt-0">{children}</h4>,
  h3: ({ children }) => <h5 className="mb-1.5 mt-4 text-[15px] font-semibold text-ink first:mt-0">{children}</h5>,
  h4: ({ children }) => <h6 className="mb-1 mt-3 text-sm font-semibold text-ink first:mt-0">{children}</h6>,
  p: ({ children }) => <p className="my-2.5 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="my-2.5 list-disc space-y-1 pl-5 marker:text-muted">{children}</ul>,
  ol: ({ children }) => <ol className="my-2.5 list-decimal space-y-1 pl-5 marker:text-muted">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  a: ({ href, children }) =>
  <a href={href} target="_blank" rel="noreferrer" className="text-accent underline-offset-2 hover:underline">
      {children}
    </a>,

  blockquote: ({ children }) => <blockquote className="my-3 border-l-2 border-accent/60 pl-3 text-muted">{children}</blockquote>,
  hr: () => <hr className="my-4 border-line" />,
  code: ({ className, children }) =>
  className ?
  <code className="block overflow-x-auto whitespace-pre rounded-lg bg-canvas p-3 text-[13px]">{children}</code> :
  <code className="rounded bg-raised px-1 py-0.5 text-[13px]">{children}</code>,

  pre: ({ children }) => <pre className="my-3">{children}</pre>,
  table: ({ children }) =>
  <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>,

  th: ({ children }) => <th className="border-b border-line px-3 py-2 text-left font-medium text-muted">{children}</th>,
  td: ({ children }) => <td className="border-b border-line/60 px-3 py-2 align-top">{children}</td>
};

export function Markdown({ children }: {children: string;}) {
  return (
    <div className="text-[15px] text-ink/90">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>);

}
