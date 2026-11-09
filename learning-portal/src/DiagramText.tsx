import { useLayoutEffect, useRef, useState, type SVGProps } from "react";

let measuringContext: CanvasRenderingContext2D | null | undefined;

export function DiagramText({ text, maxWidth, ...props }: SVGProps<SVGTextElement> & { text: string; maxWidth: number }) {
  const ref = useRef<SVGTextElement>(null);
  const [label, setLabel] = useState(text);
  useLayoutEffect(() => {
    if (!ref.current) return;
    measuringContext ??= document.createElement("canvas").getContext("2d");
    if (!measuringContext) return;
    const style = getComputedStyle(ref.current);
    measuringContext.font = style.font;
    const spacing = parseFloat(style.letterSpacing) || 0;
    const width = (value: string) => measuringContext!.measureText(value).width + Math.max(0, [...value].length - 1) * spacing;
    const fitted = [...text];
    if (width(text) <= maxWidth - 2) { setLabel(text); return; }
    while (fitted.length && width(`${fitted.join("")}…`) > maxWidth - 2) fitted.pop();
    setLabel(`${fitted.join("")}…`);
  }, [text, maxWidth]);
  return <text {...props} ref={ref} aria-label={text}>{label}</text>;
}
