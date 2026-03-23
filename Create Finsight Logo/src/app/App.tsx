import { FinSightLogo } from "./components/FinSightLogo";
import { FloatingCurrencies } from "./components/FloatingCurrencies";

export default function App() {
  return (
    <div className="size-full min-h-screen bg-gradient-to-br from-[#f0f4f8] via-[#e8eef5] to-[#dce6f0] overflow-auto relative">
      <FloatingCurrencies />

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center justify-center py-24 px-6">
        <FinSightLogo size="xl" showTagline />

        <div className="mt-8 flex items-center gap-3">
          {[
            { s: "$", c1: "#1B2A4A", c2: "#1A5276" },
            { s: "€", c1: "#1A5276", c2: "#148F77" },
            { s: "£", c1: "#148F77", c2: "#1ABC9C" },
            { s: "¥", c1: "#2980B9", c2: "#1B2A4A" },
            { s: "₹", c1: "#1ABC9C", c2: "#2980B9" },
            { s: "₩", c1: "#5D6D7E", c2: "#148F77" },
          ].map((item, i) => (
            <span
              key={i}
              className="w-9 h-9 rounded-full flex items-center justify-center text-white"
              style={{
                fontSize: "0.9rem",
                fontWeight: 600,
                background: `linear-gradient(135deg, ${item.c1}, ${item.c2})`,
              }}
            >
              {item.s}
            </span>
          ))}
        </div>
      </section>

      {/* Showcase */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Sizes */}
          <Card title="Size Variants">
            <div className="flex flex-col gap-6 items-start">
              <FinSightLogo size="large" showTagline />
              <FinSightLogo size="default" />
              <FinSightLogo size="small" />
            </div>
          </Card>

          {/* Dark */}
          <Card title="Dark Context" dark>
            <div className="flex flex-col gap-6 items-start">
              <FinSightLogo size="large" theme="dark" showTagline />
              <FinSightLogo size="default" theme="dark" />
              <FinSightLogo size="small" theme="dark" />
            </div>
          </Card>

          {/* Icon Variants */}
          <Card title="Icon Mark">
            <div className="flex items-end gap-6">
              <FinSightLogo size="xl" variant="icon" />
              <FinSightLogo size="large" variant="icon" />
              <FinSightLogo size="default" variant="icon" />
              <FinSightLogo size="small" variant="icon" />
            </div>
          </Card>

          {/* Wordmark */}
          <Card title="Wordmark">
            <div className="flex flex-col gap-3">
              <FinSightLogo size="large" variant="wordmark" showTagline />
              <FinSightLogo size="default" variant="wordmark" />
              <FinSightLogo size="small" variant="wordmark" />
            </div>
          </Card>

          {/* Navigation Contexts */}
          <div className="md:col-span-2">
            <Card title="Navigation Context">
              <div className="flex items-center justify-between bg-gradient-to-r from-[#0D1B2A] to-[#1B2A4A] rounded-xl px-6 py-4">
                <FinSightLogo size="small" theme="dark" />
                <div className="flex gap-6" style={{ fontSize: "0.8rem" }}>
                  {["Dashboard", "Markets", "Portfolio", "Analytics"].map((t) => (
                    <span key={t} className="text-[#7B8FA3] hover:text-white cursor-pointer transition-colors">{t}</span>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between bg-white/80 backdrop-blur border border-[#d5dde5] rounded-xl px-6 py-4 mt-3">
                <FinSightLogo size="small" />
                <div className="flex gap-6" style={{ fontSize: "0.8rem" }}>
                  {["Dashboard", "Markets", "Portfolio", "Analytics"].map((t) => (
                    <span key={t} className="text-[#5D6D7E] hover:text-[#1B2A4A] cursor-pointer transition-colors">{t}</span>
                  ))}
                </div>
              </div>
            </Card>
          </div>

          {/* Integration Guide */}
          <div className="md:col-span-2">
            <Card title="How to Integrate into Your Website">
              <div className="space-y-5 text-[#3D4F63]" style={{ fontSize: "0.85rem", lineHeight: 1.7 }}>
                <div>
                  <p className="text-[#1B2A4A] mb-1.5" style={{ fontWeight: 700 }}>1. Import the component</p>
                  <code className="block bg-[#0D1B2A] text-[#1ABC9C] px-4 py-3 rounded-lg" style={{ fontSize: "0.78rem" }}>
                    {`import { FinSightLogo } from "./components/FinSightLogo";`}
                  </code>
                </div>

                <div>
                  <p className="text-[#1B2A4A] mb-1.5" style={{ fontWeight: 700 }}>2. Use in a navigation bar</p>
                  <code className="block bg-[#0D1B2A] text-[#1ABC9C] px-4 py-3 rounded-lg whitespace-pre" style={{ fontSize: "0.78rem" }}>
{`<nav className="flex items-center justify-between px-6 py-3">
  <FinSightLogo size="small" theme="dark" />
  {/* ... nav links */}
</nav>`}
                  </code>
                </div>

                <div>
                  <p className="text-[#1B2A4A] mb-1.5" style={{ fontWeight: 700 }}>3. Available props</p>
                  <div className="bg-[#f6f8fa] border border-[#d5dde5] rounded-lg overflow-hidden">
                    <table className="w-full" style={{ fontSize: "0.78rem" }}>
                      <thead>
                        <tr className="bg-[#edf1f5]">
                          <th className="text-left px-4 py-2 text-[#1B2A4A]">Prop</th>
                          <th className="text-left px-4 py-2 text-[#1B2A4A]">Options</th>
                          <th className="text-left px-4 py-2 text-[#1B2A4A]">Default</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["size", '"small" | "default" | "large" | "xl"', '"default"'],
                          ["variant", '"full" | "icon" | "wordmark"', '"full"'],
                          ["theme", '"light" | "dark"', '"light"'],
                          ["animated", "true | false", "true"],
                          ["showTagline", "true | false", "false"],
                        ].map(([prop, options, def]) => (
                          <tr key={prop} className="border-t border-[#e0e5eb]">
                            <td className="px-4 py-2 font-mono text-[#2980B9]">{prop}</td>
                            <td className="px-4 py-2 font-mono text-[#5D6D7E]">{options}</td>
                            <td className="px-4 py-2 font-mono text-[#148F77]">{def}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <p className="text-[#1B2A4A] mb-1.5" style={{ fontWeight: 700 }}>4. Common usage examples</p>
                  <code className="block bg-[#0D1B2A] text-[#1ABC9C] px-4 py-3 rounded-lg whitespace-pre" style={{ fontSize: "0.78rem" }}>
{`{/* Hero / Landing page */}
<FinSightLogo size="xl" showTagline />

{/* Sidebar */}
<FinSightLogo size="small" />

{/* Favicon / App icon */}
<FinSightLogo size="small" variant="icon" />

{/* Dark dashboard header */}
<FinSightLogo size="default" theme="dark" />

{/* Static logo (no animations) */}
<FinSightLogo animated={false} />`}
                  </code>
                </div>
              </div>
            </Card>
          </div>

          {/* Color Palette */}
          <div className="md:col-span-2">
            <Card title="Brand Palette">
              <div className="flex flex-wrap gap-3">
                {[
                  { color: "#1B2A4A", name: "Navy" },
                  { color: "#1A5276", name: "Dark Teal" },
                  { color: "#2980B9", name: "Blue" },
                  { color: "#148F77", name: "Teal" },
                  { color: "#1ABC9C", name: "Light Teal" },
                  { color: "#5D6D7E", name: "Steel" },
                ].map((c) => (
                  <div key={c.name} className="flex flex-col items-center gap-1.5">
                    <div className="w-14 h-14 rounded-lg shadow-sm" style={{ backgroundColor: c.color }} />
                    <span className="text-[#5D6D7E]" style={{ fontSize: "0.6rem" }}>{c.name}</span>
                    <span className="text-[#a0aab4] font-mono" style={{ fontSize: "0.55rem" }}>{c.color}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}

function Card({ title, children, dark = false }: { title: string; children: React.ReactNode; dark?: boolean }) {
  return (
    <div
      className={`rounded-2xl p-6 ${dark ? "bg-gradient-to-br from-[#0D1B2A] to-[#162032]" : "bg-white/70 backdrop-blur border border-[#d5dde5]"}`}
    >
      <p
        className={`mb-5 uppercase tracking-[0.2em] ${dark ? "text-[#4A6274]" : "text-[#a0aab4]"}`}
        style={{ fontSize: "0.6rem" }}
      >
        {title}
      </p>
      {children}
    </div>
  );
}
