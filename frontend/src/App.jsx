import { useEffect, useMemo, useRef, useState } from "react";

const theme = {
  bg: "#f4efe7",
  ink: "#18222f",
  muted: "#5f6c7b",
  panel: "#fffaf3",
  line: "#d8cfc2",
  accent: "#0f766e",
  accentSoft: "#d8f3ef",
  gold: "#b7791f",
  rose: "#b94b5e",
  shadow: "0 24px 60px rgba(24, 34, 47, 0.12)",
};

const fonts = {
  body: "'Avenir Next', 'Segoe UI', sans-serif",
  display: "'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', Georgia, serif",
};

const initialHoldings = [
  {
    symbol: "AAPL",
    name: "Apple",
    shares: 42,
    price: 212.34,
    avgCost: 184.1,
    thesis: "Consumer ecosystem moat plus services margin expansion.",
    catalyst: "WWDC AI rollout and buyback support.",
    risk: "iPhone replacement cycle slows if consumer demand softens.",
    notes: ["Large-cap core", "Low turnover", "Good tax lot cushion"],
  },
  {
    symbol: "MSFT",
    name: "Microsoft",
    shares: 18,
    price: 438.52,
    avgCost: 376.84,
    thesis: "Cloud cash flow funds AI capex without stressing quality.",
    catalyst: "Azure AI monetization and Copilot attach rate.",
    risk: "Valuation is rich if enterprise AI spend pauses.",
    notes: ["AI platform exposure", "Core compounder", "High quality"],
  },
  {
    symbol: "JPM",
    name: "JPMorgan",
    shares: 35,
    price: 198.27,
    avgCost: 171.42,
    thesis: "Best-in-class bank franchise with diversified earnings.",
    catalyst: "NII resilience and capital return.",
    risk: "Credit costs rise if macro deteriorates.",
    notes: ["Financial ballast", "Dividend support", "Lower beta"],
  },
  {
    symbol: "NVDA",
    name: "NVIDIA",
    shares: 16,
    price: 118.91,
    avgCost: 92.33,
    thesis: "AI compute demand remains supply constrained.",
    catalyst: "Blackwell ramp and inference demand.",
    risk: "Position can become oversized after sharp rallies.",
    notes: ["Higher volatility", "Strong momentum", "Trim candidate"],
  },
  {
    symbol: "AMZN",
    name: "Amazon",
    shares: 14,
    price: 187.62,
    avgCost: 163.25,
    thesis: "Retail margins and AWS cash flow support long-duration growth.",
    catalyst: "AWS acceleration and advertising expansion.",
    risk: "Margin upside fades if consumer spending slows.",
    notes: ["Consumer plus cloud", "Secular growth", "Execution heavy"],
  },
  {
    symbol: "GOOGL",
    name: "Alphabet",
    shares: 20,
    price: 171.44,
    avgCost: 145.8,
    thesis: "Search cash flows fund AI investment without leverage stress.",
    catalyst: "AI product adoption and cloud operating leverage.",
    risk: "AI competition pressures search economics.",
    notes: ["Cash-rich", "Ad cyclical", "AI optionality"],
  },
  {
    symbol: "LLY",
    name: "Eli Lilly",
    shares: 8,
    price: 804.15,
    avgCost: 712.4,
    thesis: "Obesity and diabetes franchise drives multi-year earnings growth.",
    catalyst: "Manufacturing scale and expanded indications.",
    risk: "High expectations leave little room for execution misses.",
    notes: ["Healthcare growth", "Premium multiple", "Lower correlation"],
  },
  {
    symbol: "XOM",
    name: "Exxon Mobil",
    shares: 26,
    price: 109.32,
    avgCost: 101.7,
    thesis: "Cash generation and capital discipline support shareholder returns.",
    catalyst: "Production growth and oil price support.",
    risk: "Commodity exposure can drag if crude weakens.",
    notes: ["Energy hedge", "Dividend support", "Cyclical"],
  },
];

const seedMessages = {
  AAPL: [
    {
      role: "advisor",
      text: "Apple is acting like a stable core holding. The key question is whether you still underwrite services growth rather than just hardware replacement.",
    },
  ],
  MSFT: [
    {
      role: "advisor",
      text: "Microsoft fits a high-quality compounder bucket. I would use the chat to test whether valuation and AI monetization still justify the weight.",
    },
  ],
  JPM: [
    {
      role: "advisor",
      text: "JPMorgan gives your portfolio balance versus pure tech. Focus on credit quality, capital returns, and how much macro risk you want in the portfolio.",
    },
  ],
  NVDA: [
    {
      role: "advisor",
      text: "NVIDIA likely drives a lot of portfolio variance. The immediate adviser question is sizing discipline, not just whether the business is strong.",
    },
  ],
  AMZN: [
    {
      role: "advisor",
      text: "Amazon is a mixed consumer and cloud position, so the right question is which segment you are really underwriting at this valuation.",
    },
  ],
  GOOGL: [
    {
      role: "advisor",
      text: "Alphabet is a cash-rich AI transition story. The adviser focus should be whether AI changes the economics of its search moat.",
    },
  ],
  LLY: [
    {
      role: "advisor",
      text: "Eli Lilly adds healthcare growth to the portfolio. The key issue is whether the multiple already assumes near-perfect execution.",
    },
  ],
  XOM: [
    {
      role: "advisor",
      text: "Exxon Mobil adds cyclical balance and cash yield. You should test whether you want it as a hedge or as a conviction bet on energy prices.",
    },
  ],
};

const portfolioSeedMessages = [
  {
    role: "advisor",
    text: "Your portfolio looks tilted toward large-cap quality and AI-linked growth. The main portfolio-level questions are concentration, sector balance, and whether each holding still earns its weight.",
  },
];

const defaultHoldingFields = {
  thesis: "Awaiting thesis notes from the uploaded portfolio.",
  catalyst: "Awaiting catalyst notes from the uploaded portfolio.",
  risk: "Awaiting risk notes from the uploaded portfolio.",
  notes: ["Imported from CSV"],
};

function money(value) {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });
}

function pct(value) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function buildReply(holding, prompt) {
  const text = prompt.toLowerCase();

  if (text.includes("buy") || text.includes("add")) {
    return `If you add ${holding.symbol}, I would treat it as an incremental thesis check. Compare current price ${money(holding.price)} against your average cost ${money(holding.avgCost)} and decide whether you are averaging up because conviction improved, not because momentum feels good.`;
  }

  if (text.includes("sell") || text.includes("trim")) {
    return `For ${holding.symbol}, trim logic should be driven by sizing or thesis drift. If the thesis still holds, a partial trim is cleaner than a full exit when concentration is the main issue.`;
  }

  if (text.includes("risk")) {
    return `The main risk for ${holding.symbol} is: ${holding.risk} I would also ask whether this position is correlated with your other holdings and whether that hidden concentration is acceptable.`;
  }

  if (text.includes("thesis") || text.includes("why")) {
    return `Your current thesis reads: ${holding.thesis} The adviser angle is to define one measurable condition that would prove this thesis wrong within the next 2 quarters.`;
  }

  return `For ${holding.symbol}, I would frame the next decision around three points: thesis durability, valuation versus expected growth, and target position size in the full portfolio.`;
}

function buildPortfolioReply(prompt, stats) {
  const text = prompt.toLowerCase();

  if (text.includes("risk") || text.includes("risky")) {
    return "At the portfolio level, the biggest risk is concentration in mega-cap growth and AI-related names. I would check whether that overlap is intentional and whether you want more balance from healthcare, financials, or cash.";
  }

  if (text.includes("divers") || text.includes("balance")) {
    return "The portfolio is diversified across several sectors, but the dollar exposure still leans heavily toward technology and growth. Diversification is not just ticker count, it is how differently those positions behave in the same market regime.";
  }

  if (text.includes("best") || text.includes("strongest")) {
    return "The strongest portfolio holdings appear to be the high-conviction compounders like MSFT and AAPL, while NVDA likely contributes the most upside and the most sizing pressure.";
  }

  if (text.includes("cash") || text.includes("deploy")) {
    return `If you are deploying fresh capital into a portfolio worth ${money(stats.value)}, I would add only where conviction improved or where the current weight is still below the intended target size.`;
  }

  return "At the overall portfolio level, I would focus on three questions: where you are overexposed, which holdings deserve additional capital, and what would break the portfolio thesis over the next year.";
}

function parseCsvLine(line) {
  const cells = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  cells.push(current.trim());
  return cells;
}

function parsePortfolioCsv(text) {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (rows.length < 2) {
    throw new Error("CSV must include a header row and at least one holding.");
  }

  const headers = parseCsvLine(rows[0]).map((header) =>
    header.toLowerCase().replace(/[\s_-]+/g, ""),
  );
  const required = ["symbol", "shares", "price", "avgcost"];

  for (const field of required) {
    if (!headers.includes(field)) {
      throw new Error(`CSV is missing required column: ${field}`);
    }
  }

  const parsedHoldings = rows.slice(1).map((row, index) => {
    const cells = parseCsvLine(row);
    const record = Object.fromEntries(headers.map((header, headerIndex) => [header, cells[headerIndex] ?? ""]));
    const symbol = record.symbol.toUpperCase();
    const shares = Number(record.shares);
    const price = Number(record.price);
    const avgCost = Number(record.avgcost);

    if (!symbol || Number.isNaN(shares) || Number.isNaN(price) || Number.isNaN(avgCost)) {
      throw new Error(`Row ${index + 2} has invalid symbol, shares, price, or avgCost values.`);
    }

    return {
      symbol,
      name: record.name || symbol,
      shares,
      price,
      avgCost,
      thesis: record.thesis || defaultHoldingFields.thesis,
      catalyst: record.catalyst || defaultHoldingFields.catalyst,
      risk: record.risk || defaultHoldingFields.risk,
      notes: record.notes
        ? record.notes.split("|").map((note) => note.trim()).filter(Boolean)
        : defaultHoldingFields.notes,
    };
  });

  if (!parsedHoldings.length) {
    throw new Error("CSV did not produce any holdings.");
  }

  return parsedHoldings;
}

function App() {
  const fileInputRef = useRef(null);
  const [holdings, setHoldings] = useState(initialHoldings);
  const [view, setView] = useState("portfolio");
  const [selectedSymbol, setSelectedSymbol] = useState(initialHoldings[0].symbol);
  const [draft, setDraft] = useState("");
  const [portfolioDraft, setPortfolioDraft] = useState("");
  const [isPortfolioChatExpanded, setIsPortfolioChatExpanded] = useState(false);
  const [isHoldingChatExpanded, setIsHoldingChatExpanded] = useState(false);
  const [messagesBySymbol, setMessagesBySymbol] = useState(seedMessages);
  const [portfolioMessages, setPortfolioMessages] = useState(portfolioSeedMessages);
  const [uploadMessage, setUploadMessage] = useState("");

  const selectedHolding = useMemo(
    () => holdings.find((holding) => holding.symbol === selectedSymbol) ?? holdings[0],
    [holdings, selectedSymbol],
  );

  const portfolioStats = useMemo(() => {
    const value = holdings.reduce((sum, holding) => sum + holding.shares * holding.price, 0);
    const cost = holdings.reduce((sum, holding) => sum + holding.shares * holding.avgCost, 0);
    const largestHolding = holdings.reduce(
      (largest, holding) =>
        !largest || holding.shares * holding.price > largest.shares * largest.price ? holding : largest,
      null,
    );
    const pnl = value - cost;
    return {
      value,
      pnl,
      pnlPct: cost ? (pnl / cost) * 100 : 0,
      cost,
      largestHolding,
    };
  }, [holdings]);

  const currentMessages = messagesBySymbol[selectedHolding.symbol] ?? [];

  useEffect(() => {
    if (!uploadMessage) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setUploadMessage("");
    }, 2600);

    return () => window.clearTimeout(timeoutId);
  }, [uploadMessage]);

  function openHolding(symbol) {
    setSelectedSymbol(symbol);
    setView("holding");
  }

  function submitMessage() {
    const prompt = draft.trim();

    if (!prompt) {
      return;
    }

    const reply = buildReply(selectedHolding, prompt);

    setMessagesBySymbol((current) => ({
      ...current,
      [selectedHolding.symbol]: [
        ...(current[selectedHolding.symbol] ?? []),
        { role: "user", text: prompt },
        { role: "advisor", text: reply },
      ],
    }));
    setDraft("");
  }

  function submitPortfolioMessage() {
    const prompt = portfolioDraft.trim();

    if (!prompt) {
      return;
    }

    const reply = buildPortfolioReply(prompt, portfolioStats);

    setPortfolioMessages((current) => [
      ...current,
      { role: "user", text: prompt },
      { role: "advisor", text: reply },
    ]);
    setPortfolioDraft("");
  }

  function handlePortfolioUpload(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      try {
        const parsedHoldings = parsePortfolioCsv(String(reader.result ?? ""));
        const nextMessages = Object.fromEntries(
          parsedHoldings.map((holding) => [
            holding.symbol,
            messagesBySymbol[holding.symbol] ?? [
              {
                role: "advisor",
                text: `${holding.symbol} was imported from your CSV. Use this chat to review thesis, sizing, and risk for the position.`,
              },
            ],
          ]),
        );

        setHoldings(parsedHoldings);
        setMessagesBySymbol(nextMessages);
        setSelectedSymbol(parsedHoldings[0].symbol);
        setView("portfolio");
        setUploadMessage(`Imported ${parsedHoldings.length} holdings from ${file.name}.`);
      } catch (error) {
        setUploadMessage(error instanceof Error ? error.message : "Unable to parse the uploaded CSV.");
      } finally {
        event.target.value = "";
      }
    };

    reader.onerror = () => {
      setUploadMessage("Failed to read the selected CSV file.");
      event.target.value = "";
    };

    reader.readAsText(file);
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top left, #fff5df 0%, #f4efe7 45%, #efe5d8 100%)",
        color: theme.ink,
        fontFamily: fonts.body,
      }}
    >
      <div
        style={{
          maxWidth: 1240,
          margin: "0 auto",
          padding: "32px 20px 180px",
        }}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
            marginBottom: 28,
            flexWrap: "wrap",
          }}
        >
          <div>
            <h1
              style={{
                fontSize: "clamp(2rem, 5vw, 4rem)",
                lineHeight: 0.95,
                marginBottom: 10,
                fontFamily: fonts.display,
                fontWeight: 700,
                letterSpacing: "-0.04em",
              }}
            >
              Meridian Portfolio
            </h1>
            <p style={{ color: theme.muted, maxWidth: 700, fontSize: 17 }}>
              Review your portfolio on the home screen, open any holding, and chat with the adviser alongside the position details.
            </p>
          </div>

        </header>
        {view === "portfolio" ? (
          <div style={{ display: "grid", gap: 20 }}>
            <section
              style={{
                display: "block",
              }}
            >
              <div
                style={{
                  background: theme.panel,
                  border: `1px solid ${theme.line}`,
                  borderRadius: 28,
                  padding: 28,
                  boxShadow: theme.shadow,
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(0, 1.2fr) minmax(320px, 0.8fr)",
                    gap: 24,
                    alignItems: "start",
                  }}
                >
                  <div>
                    <div style={{ color: theme.muted, marginBottom: 12 }}>Portfolio overview</div>
                    <div style={{ fontSize: "clamp(2rem, 4vw, 3.5rem)", fontWeight: 700 }}>
                      {money(portfolioStats.value)}
                    </div>
                    <div style={{ display: "flex", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
                      <StatChip label="Unrealized P/L" value={money(portfolioStats.pnl)} tone="accent" />
                      <StatChip label="Return" value={pct(portfolioStats.pnlPct)} tone="gold" />
                      <StatChip label="Holdings" value={`${holdings.length}`} tone="rose" />
                    </div>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                      gap: 14,
                    }}
                  >
                    <InfoCard label="Largest position" value={portfolioStats.largestHolding?.symbol ?? "—"} />
                    <InfoCard label="Imported holdings" value={`${holdings.length}`} />
                    <InfoCard label="Portfolio return" value={pct(portfolioStats.pnlPct)} />
                    <InfoCard label="Estimated cost basis" value={money(portfolioStats.cost)} />
                  </div>
                </div>
              </div>
            </section>

            <section
              style={{
                display: "block",
              }}
            >
              <div
                style={{
                  background: "rgba(255, 250, 243, 0.8)",
                  border: `1px solid ${theme.line}`,
                  borderRadius: 28,
                  padding: 22,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 18,
                    flexWrap: "wrap",
                  }}
                >
                  <div>
                    <h2 style={{ fontSize: 24, marginBottom: 4 }}>Holdings</h2>
                    <div style={{ color: theme.muted, fontSize: 14 }}>
                      Open any holding for stock-specific analysis
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={handlePortfolioUpload}
                      style={{ display: "none" }}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      style={{
                        border: `1px solid ${theme.line}`,
                        background: "#fffdf8",
                        color: theme.ink,
                        borderRadius: 999,
                        padding: "10px 16px",
                        cursor: "pointer",
                        fontWeight: 600,
                        boxShadow: "0 10px 24px rgba(24, 34, 47, 0.06)",
                      }}
                    >
                      Upload Portfolio CSV
                    </button>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  {holdings.map((holding) => {
                    const marketValue = holding.shares * holding.price;
                    const gainPct = ((holding.price - holding.avgCost) / holding.avgCost) * 100;

                    return (
                      <button
                        key={holding.symbol}
                        onClick={() => openHolding(holding.symbol)}
                        style={{
                          textAlign: "left",
                          border: `1px solid ${theme.line}`,
                          borderRadius: 24,
                          padding: 18,
                          background: "#fffdf8",
                          cursor: "pointer",
                          boxShadow: "0 12px 32px rgba(24, 34, 47, 0.08)",
                          display: "grid",
                          gridTemplateColumns:
                            "minmax(0, 1.1fr) minmax(110px, 0.55fr) repeat(3, minmax(90px, 0.55fr)) minmax(0, 1.5fr)",
                          gap: 16,
                          alignItems: "center",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "flex-start",
                          }}
                        >
                          <div>
                            <div style={{ fontSize: 13, color: theme.muted }}>{holding.name}</div>
                            <div style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.05 }}>{holding.symbol}</div>
                          </div>
                        </div>

                        <ListMetric
                          label="Return"
                          value={pct(gainPct)}
                          valueColor={gainPct >= 0 ? theme.accent : theme.rose}
                        />
                        <ListMetric label="Market value" value={money(marketValue)} />
                        <ListMetric label="Shares" value={`${holding.shares}`} />
                        <ListMetric label="Avg cost" value={money(holding.avgCost)} />
                        <div style={{ color: theme.muted, lineHeight: 1.5, fontSize: 14 }}>
                          {holding.thesis}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </section>
          </div>
        ) : (
          <section
            style={{
              display: "block",
            }}
          >
            <div
              style={{
                background: "rgba(255, 250, 243, 0.86)",
                border: `1px solid ${theme.line}`,
                borderRadius: 28,
                padding: 24,
                boxShadow: theme.shadow,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                <div>
                  <button
                    onClick={() => setView("portfolio")}
                    style={{
                      border: "none",
                      background: "transparent",
                      color: theme.muted,
                      cursor: "pointer",
                      fontSize: 14,
                      padding: 0,
                      marginBottom: 18,
                    }}
                  >
                    ← Back to portfolio
                  </button>
                  <div style={{ color: theme.muted, marginBottom: 6 }}>{selectedHolding.name}</div>
                  <h2 style={{ fontSize: 42, lineHeight: 1 }}>{selectedHolding.symbol}</h2>
                </div>

                <div style={{ minWidth: 220 }}>
                  <div style={{ color: theme.muted, marginBottom: 4 }}>Current price</div>
                  <div style={{ fontSize: 32, fontWeight: 700 }}>{money(selectedHolding.price)}</div>
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: 14,
                  marginTop: 22,
                  marginBottom: 24,
                }}
              >
                <InfoCard label="Shares" value={`${selectedHolding.shares}`} />
                <InfoCard label="Average cost" value={money(selectedHolding.avgCost)} />
                <InfoCard
                  label="Unrealized return"
                  value={pct(((selectedHolding.price - selectedHolding.avgCost) / selectedHolding.avgCost) * 100)}
                />
              </div>

              <DetailBlock title="Investment thesis" text={selectedHolding.thesis} />
              <DetailBlock title="Near-term catalyst" text={selectedHolding.catalyst} />
              <DetailBlock title="Main risk" text={selectedHolding.risk} />

              <div style={{ marginTop: 24 }}>
                <div style={{ fontSize: 13, color: theme.muted, marginBottom: 10 }}>Portfolio notes</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                  {selectedHolding.notes.map((note) => (
                    <span
                      key={note}
                      style={{
                        padding: "10px 14px",
                        background: "#fffdf8",
                        borderRadius: 999,
                        border: `1px solid ${theme.line}`,
                        fontSize: 14,
                      }}
                    >
                      {note}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
      {uploadMessage && (
        <div
          style={{
            position: "fixed",
            top: 24,
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(255, 253, 248, 0.98)",
            color: theme.ink,
            padding: "12px 16px",
            borderRadius: 999,
            boxShadow: "0 18px 40px rgba(24, 34, 47, 0.14)",
            fontSize: 14,
            zIndex: 30,
            border: `1px solid ${theme.line}`,
          }}
        >
          {uploadMessage}
        </div>
      )}
      {view === "portfolio" && (
        <div
          style={{
            position: "fixed",
            right: 24,
            bottom: 24,
            width: isPortfolioChatExpanded ? "min(440px, calc(100vw - 32px))" : "min(360px, calc(100vw - 32px))",
            background: "linear-gradient(180deg, rgba(255,253,248,0.98), rgba(244,239,231,0.98))",
            borderRadius: 24,
            color: theme.ink,
            boxShadow: "0 30px 80px rgba(24, 34, 47, 0.18)",
            border: `1px solid ${theme.line}`,
            overflow: "hidden",
            zIndex: 20,
            transformOrigin: "bottom right",
            transition:
              "width 320ms cubic-bezier(0.22, 1.25, 0.36, 1), box-shadow 320ms ease, border-radius 320ms ease",
            animation: isPortfolioChatExpanded
              ? "portfolioChatElasticOpen 560ms cubic-bezier(0.18, 1.2, 0.32, 1)"
              : "portfolioChatElasticClose 420ms cubic-bezier(0.55, 0, 0.68, 1)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 18px",
              cursor: "pointer",
              background: "linear-gradient(180deg, rgba(216,243,239,0.86), rgba(255,253,248,0.92))",
            }}
            onClick={() => setIsPortfolioChatExpanded((current) => !current)}
          >
            <div>
              <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: theme.accent }}>
                Portfolio Chat
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                Ask about the full portfolio
              </div>
            </div>
            <button
              onClick={(event) => {
                event.stopPropagation();
                setIsPortfolioChatExpanded((current) => !current);
              }}
              style={{
                border: "none",
                background: "#fffdf8",
                color: theme.ink,
                borderRadius: 999,
                width: 38,
                height: 38,
                cursor: "pointer",
                fontSize: 18,
                fontWeight: 700,
                boxShadow: "0 8px 18px rgba(24, 34, 47, 0.08)",
              }}
              aria-label={isPortfolioChatExpanded ? "Minimize portfolio chat" : "Maximize portfolio chat"}
            >
              {isPortfolioChatExpanded ? "−" : "+"}
            </button>
          </div>

          {isPortfolioChatExpanded && (
            <div style={{ padding: "0 18px 18px" }}>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  flexWrap: "wrap",
                  marginBottom: 14,
                }}
              >
                {[
                  "What is my biggest portfolio risk?",
                  "Am I diversified enough?",
                  "Which holdings look strongest?",
                  "Where should new cash go?",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setPortfolioDraft(prompt)}
                    style={{
                      border: `1px solid ${theme.line}`,
                      background: "#fffdf8",
                      color: theme.ink,
                      padding: "8px 12px",
                      borderRadius: 999,
                      cursor: "pointer",
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              <div
                style={{
                  height: 260,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  paddingRight: 4,
                  marginBottom: 14,
                }}
              >
                {portfolioMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    style={{
                      alignSelf: message.role === "user" ? "flex-end" : "flex-start",
                      maxWidth: "88%",
                      background: message.role === "user" ? theme.accentSoft : "#fffdf8",
                      color: theme.ink,
                      borderRadius: 20,
                      padding: "14px 16px",
                      lineHeight: 1.55,
                      border: `1px solid ${theme.line}`,
                    }}
                  >
                    {message.text}
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 10,
                }}
              >
                <textarea
                  value={portfolioDraft}
                  onChange={(event) => setPortfolioDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submitPortfolioMessage();
                    }
                  }}
                  placeholder="Ask about allocation, concentration, or portfolio risk..."
                  rows={4}
                  style={{
                    resize: "none",
                    border: `1px solid ${theme.line}`,
                    background: "#fffdf8",
                    color: theme.ink,
                    borderRadius: 20,
                    padding: 16,
                    font: "inherit",
                  }}
                />
                <button
                  onClick={submitPortfolioMessage}
                  style={{
                    border: "none",
                    background: "#f1b04b",
                    color: "#1f2937",
                    borderRadius: 18,
                    padding: "0 18px",
                    cursor: "pointer",
                    fontWeight: 700,
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {view === "holding" && (
        <div
          style={{
            position: "fixed",
            right: 24,
            bottom: 24,
            width: isHoldingChatExpanded ? "min(440px, calc(100vw - 32px))" : "min(360px, calc(100vw - 32px))",
            background: "linear-gradient(180deg, rgba(255,253,248,0.98), rgba(244,239,231,0.98))",
            borderRadius: 24,
            color: theme.ink,
            boxShadow: "0 30px 80px rgba(24, 34, 47, 0.18)",
            border: `1px solid ${theme.line}`,
            overflow: "hidden",
            zIndex: 20,
            transformOrigin: "bottom right",
            transition:
              "width 320ms cubic-bezier(0.22, 1.25, 0.36, 1), box-shadow 320ms ease, border-radius 320ms ease",
            animation: isHoldingChatExpanded
              ? "portfolioChatElasticOpen 560ms cubic-bezier(0.18, 1.2, 0.32, 1)"
              : "portfolioChatElasticClose 420ms cubic-bezier(0.55, 0, 0.68, 1)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "16px 18px",
              cursor: "pointer",
              background: "linear-gradient(180deg, rgba(216,243,239,0.86), rgba(255,253,248,0.92))",
            }}
            onClick={() => setIsHoldingChatExpanded((current) => !current)}
          >
            <div>
              <div style={{ fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: theme.accent }}>
                Adviser Chat
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                Ask about {selectedHolding.symbol}
              </div>
            </div>
            <button
              onClick={(event) => {
                event.stopPropagation();
                setIsHoldingChatExpanded((current) => !current);
              }}
              style={{
                border: "none",
                background: "#fffdf8",
                color: theme.ink,
                borderRadius: 999,
                width: 38,
                height: 38,
                cursor: "pointer",
                fontSize: 18,
                fontWeight: 700,
                boxShadow: "0 8px 18px rgba(24, 34, 47, 0.08)",
              }}
              aria-label={isHoldingChatExpanded ? "Minimize holding chat" : "Maximize holding chat"}
            >
              {isHoldingChatExpanded ? "−" : "+"}
            </button>
          </div>

          {isHoldingChatExpanded && (
            <div style={{ padding: "0 18px 18px" }}>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  flexWrap: "wrap",
                  marginBottom: 14,
                }}
              >
                {["What is the risk?", "Should I trim?", "What is the thesis?", "Should I add more?"].map(
                  (prompt) => (
                    <button
                      key={prompt}
                      onClick={() => setDraft(prompt)}
                      style={{
                        border: `1px solid ${theme.line}`,
                        background: "#fffdf8",
                        color: theme.ink,
                        padding: "8px 12px",
                        borderRadius: 999,
                        cursor: "pointer",
                      }}
                    >
                      {prompt}
                    </button>
                  ),
                )}
              </div>

              <div
                style={{
                  height: 260,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  paddingRight: 4,
                  marginBottom: 14,
                }}
              >
                {currentMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    style={{
                      alignSelf: message.role === "user" ? "flex-end" : "flex-start",
                      maxWidth: "88%",
                      background: message.role === "user" ? theme.accentSoft : "#fffdf8",
                      color: theme.ink,
                      borderRadius: 20,
                      padding: "14px 16px",
                      lineHeight: 1.55,
                      border: `1px solid ${theme.line}`,
                    }}
                  >
                    {message.text}
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 10,
                }}
              >
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submitMessage();
                    }
                  }}
                  placeholder={`Ask the adviser about ${selectedHolding.symbol}...`}
                  rows={4}
                  style={{
                    resize: "none",
                    border: `1px solid ${theme.line}`,
                    background: "#fffdf8",
                    color: theme.ink,
                    borderRadius: 20,
                    padding: 16,
                    font: "inherit",
                  }}
                />
                <button
                  onClick={submitMessage}
                  style={{
                    border: "none",
                    background: "#f1b04b",
                    color: "#1f2937",
                    borderRadius: 18,
                    padding: "0 18px",
                    cursor: "pointer",
                    fontWeight: 700,
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      <footer
        style={{
          borderTop: `1px solid ${theme.line}`,
          background: "linear-gradient(180deg, rgba(255, 250, 243, 0.72), rgba(244, 239, 231, 0.92))",
          padding: "26px 20px 30px",
        }}
      >
        <div
          style={{
            maxWidth: 1240,
            margin: "0 auto",
            display: "grid",
            gridTemplateColumns: "minmax(0, 1.3fr) minmax(220px, 0.7fr)",
            gap: 20,
            alignItems: "start",
          }}
        >
          <div>
            <div
              style={{
                fontFamily: fonts.display,
                fontSize: 24,
                lineHeight: 1,
                color: theme.ink,
                marginBottom: 8,
              }}
            >
              Meridian Portfolio
            </div>
            <div style={{ color: theme.muted, fontSize: 14, lineHeight: 1.6, maxWidth: 640 }}>
              A financial adviser agent interface created as a course project for University of Utah
              CS 6960.
            </div>
          </div>
          <div
            style={{
              display: "grid",
              gap: 8,
              justifyItems: "start",
            }}
          >
            <div style={{ textAlign: "left" }}>
              <div
                style={{
                  color: theme.muted,
                  fontSize: 11,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                Authors
              </div>
              <div style={{ color: theme.ink, fontSize: 14, lineHeight: 1.7 }}>
                <div>Zhi-Hao Tsai</div>
                <div>Mikhail Berlay</div>
                <div>Yu Sun</div>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StatChip({ label, value, tone }) {
  const tones = {
    accent: { background: theme.accentSoft, color: theme.accent },
    gold: { background: "#fdf1dc", color: theme.gold },
    rose: { background: "#fde8ec", color: theme.rose },
  };

  return (
    <div
      style={{
        padding: "12px 16px",
        borderRadius: 18,
        ...tones[tone],
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.75 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function HoldingRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
      <span style={{ color: theme.muted, fontSize: 14 }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function ListMetric({ label, value, valueColor }) {
  return (
    <div>
      <div style={{ color: theme.muted, fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: 15, color: valueColor ?? theme.ink }}>{value}</div>
    </div>
  );
}

function InfoCard({ label, value }) {
  return (
    <div
      style={{
        background: "#fffdf8",
        border: `1px solid ${theme.line}`,
        borderRadius: 22,
        padding: 18,
      }}
    >
      <div style={{ color: theme.muted, fontSize: 13, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function DetailBlock({ title, text }) {
  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 13, color: theme.muted, marginBottom: 8 }}>{title}</div>
      <div style={{ lineHeight: 1.7, fontSize: 16 }}>{text}</div>
    </div>
  );
}

export default App;
