export function HeroArt() {
  return <div className="hero-art" aria-hidden="true"><svg viewBox="0 0 430 310" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs><linearGradient id="tile" x1="70" y1="90" x2="310" y2="270" gradientUnits="userSpaceOnUse"><stop stopColor="#e6ecf6"/><stop offset="1" stopColor="#bccae4"/></linearGradient><linearGradient id="cube" x1="130" y1="80" x2="240" y2="190"><stop stopColor="#3e6bbe"/><stop offset="1" stopColor="#193f86"/></linearGradient><filter id="soft"><feGaussianBlur stdDeviation="12"/></filter></defs>
    <ellipse cx="226" cy="260" rx="143" ry="25" fill="#a4b2cd" opacity=".17" filter="url(#soft)"/>
    <path d="m43 222 172-100 173 100-173 100Z" fill="#e3e9f4" opacity=".55"/>
    <path d="m72 194 143-83 143 83-143 83Z" fill="url(#tile)" stroke="#fff" strokeWidth="2"/>
    <path d="m72 194 143 83v14L72 209Z" fill="#b9c4d8"/><path d="m358 194-143 83v14l143-82Z" fill="#9aaac8"/>
    <path d="m105 180 110-64 110 64-110 63Z" style={{ stroke: "var(--accent-line)" }} strokeDasharray="4 5"/>
    <path d="M215 91v28m0 74v26m-82-68 30 17m105-4 31-17" style={{ stroke: "var(--accent-line)" }} strokeWidth="2" strokeDasharray="4 4"/>
    <path d="m166 126 49-28 49 28-49 29Z" fill="#84a0d3"/><path d="m166 126 49 29v57l-49-29Z" fill="url(#cube)"/><path d="m264 126-49 29v57l49-29Z" fill="#284c90"/>
    <path d="m184 137 13 8v18l-13-8Zm0 28 13 8v18l-13-8Z" fill="#bccce9" opacity=".8"/><path d="m226 154 24-14v8l-24 14Zm0 16 24-14v8l-24 14Z" fill="#bccce9" opacity=".75"/>
    <path d="m105 144 28-16 28 16-28 17Z" fill="#e5c48c"/><path d="m105 144 28 17v31l-28-16Z" fill="#cfab70"/><path d="m161 144-28 17v31l28-16Z" fill="#ba955c"/>
    <path d="m274 137 28-16 28 16-28 17Z" fill="#c6d8e8"/><path d="m274 137 28 17v32l-28-16Z" fill="#8eabc5"/><path d="m330 137-28 17v32l28-16Z" fill="#698eaf"/>
    <path d="m188 65 27-16 27 16-27 16Z" fill="#fff" stroke="#bac7df"/><path d="m188 65 27 16v28l-27-16Z" fill="#dce4f2" stroke="#bac7df"/><path d="m242 65-27 16v28l27-16Z" fill="#b7c5e0" stroke="#bac7df"/>
    <circle cx="215" cy="28" r="6" fill="#c99b57"/><path d="M215 34v12" stroke="#c99b57" strokeDasharray="2 3"/>
    <g style={{ fill: "var(--muted-soft)" }}><circle cx="68" cy="124" r="3"/><circle cx="354" cy="103" r="4"/><circle cx="328" cy="245" r="3"/></g>
    <path d="m64 89 6 3-6 3-6-3Z" fill="#cba567"/><path d="m363 161 6 3-6 3-6-3Z" fill="#cba567"/>
    <text x="278" y="72" fontFamily="monospace" fontSize="10" letterSpacing="2" style={{ fill: "var(--muted)" }}>BUILD TO UNDERSTAND</text>
  </svg></div>;
}
