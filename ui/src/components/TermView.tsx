import type { Term } from "../api";

/** Renders an RDF term with colour by kind: IRIs (prefix dimmed), literals, blank nodes. */
export function TermView({ term }: { term: Term }) {
  if (term.kind === "literal") {
    const dt = term.datatype;
    const numeric = dt === "xsd:integer" || dt === "xsd:decimal" || dt === "xsd:double";
    const bool = dt === "xsd:boolean";
    return (
      <span className={`term lit ${numeric ? "num" : bool ? "bool" : "str"}`} title={term.n3}>
        {numeric || bool ? term.value : <>“{term.value}”</>}
        {dt && !numeric && !bool && dt !== "xsd:string" && <span className="dt">{dt}</span>}
      </span>
    );
  }
  if (term.kind === "bnode") {
    return (
      <span className="term bnode" title="blank node">
        {term.short}
      </span>
    );
  }
  if (term.short === "a") {
    return <span className="term kw">a</span>;
  }
  const i = term.short.indexOf(":");
  if (i > 0 && !term.short.startsWith("<")) {
    return (
      <span className="term iri" title={term.n3}>
        <span className="pfx">{term.short.slice(0, i + 1)}</span>
        {term.short.slice(i + 1)}
      </span>
    );
  }
  return (
    <span className="term iri" title={term.n3}>
      {term.short}
    </span>
  );
}

export function TripleLine({ s, p, o }: { s: Term; p: Term; o: Term }) {
  return (
    <span className="triple-line">
      <TermView term={s} /> <TermView term={p} /> <TermView term={o} />
    </span>
  );
}
