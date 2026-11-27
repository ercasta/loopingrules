import { useState } from "react";
import { api, type PendingCall } from "../api";

/** One pending tool call: approve once, reject, or trust a command template. */
export function ApprovalBanner({ call, onError }: { call: PendingCall; onError: (e: unknown) => void }) {
  const [remember, setRemember] = useState<string | null>(null);

  return (
    <div className="approval">
      <div className="approval-main">
        <span className="badge">⚙ {call.tool}</span>
        <span className="label">wants to run</span>
        <code>{call.command}</code>
        <span className="spacer" />
        <button className="btn approve" onClick={() => api.decide(call.id, true).catch(onError)}>
          ✓ Approve
        </button>
        <button
          className="btn ghost"
          onClick={() => setRemember(remember === null ? call.suggested : null)}
          title="Trust every command matching a template"
        >
          ★ Always allow…
        </button>
        <button className="btn ghost" onClick={() => api.decide(call.id, false).catch(onError)}>
          ✕ Reject
        </button>
      </div>
      {remember !== null && (
        <form
          className="remember"
          onSubmit={(e) => {
            e.preventDefault();
            api.decide(call.id, true, remember).catch(onError);
          }}
        >
          <span className="label">trust commands matching</span>
          <input value={remember} onChange={(e) => setRemember(e.target.value)} spellCheck={false} />
          <button className="btn approve">Trust &amp; approve</button>
          <span className="note">
            each <code>'{"{}"}'</code> matches one quoted argument; nothing can be appended
          </span>
        </form>
      )}
    </div>
  );
}
