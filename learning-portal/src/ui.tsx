import type { ButtonHTMLAttributes, ReactNode } from "react";

const paths: Record<string, string> = {
  arrow: "M5 12h14m-6-6 6 6-6 6",
  check: "m5 12 4 4L19 6",
  book: "M12 5v15M12 5C8 2 4 3 2 4v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-2-1-6-2-10 1Z",
  layers: "m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5",
  clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  spark: "m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3Z",
  note: "M8 4H4v17h16V4h-4M8 2h8v5H8V2Zm0 10h8m-8 4h5",
  shield: "M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4Zm-4 10 3 3 5-6",
  chevron: "m9 5 7 7-7 7",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "m6 6 12 12M6 18 18 6",
  refresh: "M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 4M4 15l2 4a7 7 0 0 0 12-2",
  terminal: "m5 6 5 6-5 6m8 0h6",
  external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7",
};

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.book} /></svg>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { icon?: string; children: ReactNode };
export function Button({ icon, children, type = "button", ...props }: ButtonProps) {
  return <button type={type} {...props}>{icon && <Icon name={icon} size={18} />}<span>{children}</span></button>;
}

export function SectionHeading({ kicker, title, description, children }: { kicker: string; title: string; description?: string; children?: ReactNode }) {
  return <div className="section-heading"><p className="eyebrow">{kicker}</p><h2>{title}</h2>{description && <p className="section-description">{description}</p>}{children}</div>;
}

export const number = (index: number) => String(index).padStart(2, "0");
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : "処理できませんでした。もう一度お試しください。";
export type Notify = (message: string, failure?: boolean) => void;
