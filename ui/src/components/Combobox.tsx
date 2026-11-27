import { forwardRef, useEffect, useRef, useState } from "react";
import type { Suggestion } from "../api";

type Props = {
  value: string;
  onChange: (v: string) => void;
  /** Fetch suggestions for the current text. */
  load: (q: string) => Promise<Suggestion[]>;
  /** Changes when the context (e.g. the subject) changes, to refetch. */
  contextKey: string;
  placeholder: string;
  invalid?: string | null;
  onPicked?: () => void;
};

/** A text input with a dropdown of typed suggestions; opens upwards. */
export const Combobox = forwardRef<HTMLInputElement, Props>(function Combobox(p, ref) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      p.load(p.value)
        .then((xs) => {
          setItems(xs);
          setActive(0);
        })
        .catch(() => setItems([]));
    }, 100);
    return () => window.clearTimeout(timer.current);
  }, [open, p.value, p.contextKey]);

  useEffect(() => {
    listRef.current?.querySelector(".active")?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const pick = (s: Suggestion) => {
    p.onChange(s.value);
    setOpen(false);
    p.onPicked?.();
  };

  const visible = open && items.length > 0;

  return (
    <span className={`combo ${p.invalid ? "invalid" : ""}`}>
      <input
        ref={ref}
        value={p.value}
        placeholder={p.placeholder}
        onChange={(e) => {
          p.onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!visible) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(items.length - 1, a + 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(0, a - 1));
          } else if ((e.key === "Enter" || e.key === "Tab") && items[active] && items[active].value !== p.value) {
            e.preventDefault();
            pick(items[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        title={p.invalid ?? undefined}
      />
      {visible && (
        <ul className="combo-list" ref={listRef}>
          {items.map((s, i) => (
            <li
              key={s.value}
              className={`${i === active ? "active" : ""} ${s.status ?? ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(s);
              }}
              onMouseEnter={() => setActive(i)}
            >
              <span className="v">{s.value}</span>
              {s.status === "missing" && <span className="badge req">required</span>}
              {s.status === "full" && <span className="badge full">full</span>}
              <span className="h">{s.hint}</span>
            </li>
          ))}
        </ul>
      )}
    </span>
  );
});
