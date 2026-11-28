import { useEffect, useRef, useState } from "react";
import { api, type Message } from "../api";
import { TermView } from "./TermView";

type Props = {
  out: Message[];
  waiting: number;
  onError: (e: unknown) => void;
};

const EXAMPLE = "[] a ex:Request ;\n   ex:about ex:thing .";

/** The lr:in / lr:out channels (design D25): send messages to the model, read its answers. */
export function IOPanel({ out, waiting, onError }: Props) {
  const [draft, setDraft] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLOListElement>(null);
  const newest = out[out.length - 1]?.id;

  // Keep the newest message in view, like a chat.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [newest]);

  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    try {
      await api.post(draft);
      setDraft("");
      setProblem(null);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="io">
      <ol className="io-out" ref={listRef}>
        {out.length === 0 && <li className="empty">No messages from the model.</li>}
        {out.map((m) => (
          <li key={m.id} title={m.short}>
            {m.text !== null ? (
              <div className="io-text">{m.text}</div>
            ) : (
              <div className="io-triples">
                {m.triples.map((t) => (
                  <div key={t.key}>
                    <TermView term={t.s} /> <TermView term={t.p} /> <TermView term={t.o} />
                  </div>
                ))}
              </div>
            )}
            <span className="io-meta">{m.types.filter((t) => t !== "lr:Say").join(" ")}</span>
          </li>
        ))}
      </ol>
      <div className="io-bar">
        <span className="io-waiting" title="Messages on lr:in that no operation has consumed yet">
          {waiting > 0 ? `${waiting} waiting in lr:in` : ""}
        </span>
        {out.length > 0 && (
          <button className="btn ghost small" onClick={() => api.ack().catch(onError)} title="Acknowledge (delete) every lr:out message">
            Clear
          </button>
        )}
      </div>
      <form
        className="io-in"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          value={draft}
          placeholder={EXAMPLE}
          rows={3}
          spellCheck={false}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button className="btn primary" disabled={!draft.trim() || sending} title="Post to lr:in (Ctrl+Enter)">
          Send
        </button>
      </form>
      {problem && <div className="assist problem io-problem">⚠ {problem}</div>}
    </div>
  );
}
