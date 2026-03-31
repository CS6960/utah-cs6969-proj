import { useEffect, useMemo, useRef, useState } from "react";
import fallbackHoldings, { FALLBACK_GENERATED_AT } from "./fallbackHoldings";

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

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(text) {
  return escapeHtml(text)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function markdownToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let inCodeBlock = false;
  let codeLines = [];
  let paragraphLines = [];
  let listType = null;
  let listItems = [];

  function flushParagraph() {
    if (!paragraphLines.length) {
      return;
    }

    const paragraphHtml = renderInlineMarkdown(paragraphLines.join("\n")).replace(/\n/g, "<br />");
    blocks.push(`<p>${paragraphHtml}</p>`);
    paragraphLines = [];
  }

  function flushList() {
    if (!listItems.length || !listType) {
      return;
    }

    const itemsHtml = listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("");
    blocks.push(`<${listType}>${itemsHtml}</${listType}>`);
    listItems = [];
    listType = null;
  }

  function flushCodeBlock() {
    if (!codeLines.length) {
      return;
    }

    blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  }

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();

      if (inCodeBlock) {
        flushCodeBlock();
      }

      inCodeBlock = !inCodeBlock;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.*)$/);
    const orderedMatch = line.match(/^\s*\d+\.\s+(.*)$/);

    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      const nextListType = unorderedMatch ? "ul" : "ol";

      if (listType && listType !== nextListType) {
        flushList();
      }

      listType = nextListType;
      listItems.push((unorderedMatch ?? orderedMatch)[1]);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraphLines.push(line);
  }

  flushParagraph();
  flushList();

  if (inCodeBlock) {
    flushCodeBlock();
  }

  return blocks.join("");
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
  const [holdings, setHoldings] = useState(fallbackHoldings);
  const [lastPriceUpdate, setLastPriceUpdate] = useState(FALLBACK_GENERATED_AT);
  const [view, setView] = useState("portfolio");
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [draft, setDraft] = useState("");
  const [portfolioDraft, setPortfolioDraft] = useState("");
  const [isHoldingChatLoading, setIsHoldingChatLoading] = useState(false);
  const [isPortfolioChatLoading, setIsPortfolioChatLoading] = useState(false);
  const [isPortfolioLoading, setIsPortfolioLoading] = useState(true);
  const [portfolioError, setPortfolioError] = useState("");
  const [chatError, setChatError] = useState("");
  const [isPortfolioChatExpanded, setIsPortfolioChatExpanded] = useState(false);
  const [isHoldingChatExpanded, setIsHoldingChatExpanded] = useState(false);
  const [messagesBySymbol, setMessagesBySymbol] = useState(seedMessages);
  const [portfolioMessages, setPortfolioMessages] = useState(portfolioSeedMessages);
  const [uploadMessage, setUploadMessage] = useState("");
  const [dataSource, setDataSource] = useState("api");

  const chatApiBase = useMemo(() => {
    const envBase = import.meta.env.VITE_API_BASE;
    if (envBase !== undefined) return envBase;

    if (typeof window !== "undefined") {
      const { hostname } = window.location;

      if (hostname === "localhost" || hostname === "127.0.0.1") {
        return "http://localhost:8000";
      }
    }

    return "https://utah-cs6969-proj.onrender.com";
  }, []);

  const selectedHolding = useMemo(
    () => holdings.find((holding) => holding.symbol === selectedSymbol) ?? holdings[0] ?? null,
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

  const currentMessages = selectedHolding ? messagesBySymbol[selectedHolding.symbol] ?? [] : [];

  useEffect(() => {
    if (!holdings.length) {
      setSelectedSymbol("");
      return;
    }

    if (!selectedSymbol || !holdings.some((holding) => holding.symbol === selectedSymbol)) {
      setSelectedSymbol(holdings[0].symbol);
    }
  }, [holdings, selectedSymbol]);

  useEffect(() => {
    if (dataSource !== "api") {
      setIsPortfolioLoading(false);
      setPortfolioError("");
      return undefined;
    }

    let isDisposed = false;

    async function loadPortfolio() {
      setPortfolioError("");
      setIsPortfolioLoading(true);

      try {
        const response = await fetch(`${chatApiBase}/api/portfolio`);

        if (!response.ok) {
          throw new Error(`Portfolio request failed with ${response.status}`);
        }

        const data = await response.json();
        const nextHoldings = Array.isArray(data?.holdings) ? data.holdings : [];

        if (!nextHoldings.length) {
          throw new Error("Portfolio API returned no holdings.");
        }

        if (!isDisposed) {
          setHoldings(nextHoldings);
          setLastPriceUpdate(new Date().toISOString());
        }
      } catch (error) {
        if (!isDisposed) {
          setPortfolioError(error instanceof Error ? error.message : "Unable to load the portfolio.");
        }
      } finally {
        if (!isDisposed) {
          setIsPortfolioLoading(false);
        }
      }
    }

    loadPortfolio();
    const intervalId = window.setInterval(loadPortfolio, 300000);

    return () => {
      isDisposed = true;
      window.clearInterval(intervalId);
    };
  }, [chatApiBase, dataSource]);

  useEffect(() => {
    if (!uploadMessage) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setUploadMessage("");
    }, 2600);

    return () => window.clearTimeout(timeoutId);
  }, [uploadMessage]);

  async function openHolding(symbol) {
    setSelectedSymbol(symbol);
    setView("holding");

    if (dataSource !== "api") {
      return;
    }

    try {
      const response = await fetch(`${chatApiBase}/api/portfolio/${symbol}`);

      if (!response.ok) {
        throw new Error(`Holding request failed with ${response.status}`);
      }

      const latestHolding = await response.json();
      setHoldings((current) =>
        current.map((holding) => (holding.symbol === symbol ? { ...holding, ...latestHolding } : holding)),
      );
    } catch (error) {
      setPortfolioError(error instanceof Error ? error.message : "Unable to refresh the selected holding.");
    }
  }

  async function submitMessage() {
    const prompt = draft.trim();

    if (!prompt || isHoldingChatLoading || !selectedHolding) {
      return;
    }

    setChatError("");
    setIsHoldingChatLoading(true);
    setDraft("");

    setMessagesBySymbol((current) => ({
      ...current,
      [selectedHolding.symbol]: [
        ...(current[selectedHolding.symbol] ?? []),
        { role: "user", text: prompt },
      ],
    }));

    try {
      const response = await fetch(`${chatApiBase}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: prompt }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }

      const data = await response.json();
      const reply =
        typeof data?.result === "string"
          ? data.result
          : typeof data?.reply === "string"
            ? data.reply
            : "No reply";

      setMessagesBySymbol((current) => ({
        ...current,
        [selectedHolding.symbol]: [
          ...(current[selectedHolding.symbol] ?? []),
          { role: "advisor", text: reply },
        ],
      }));
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Unable to reach the chat service.");
    } finally {
      setIsHoldingChatLoading(false);
    }
  }

  async function submitPortfolioMessage() {
    const prompt = portfolioDraft.trim();

    if (!prompt || isPortfolioChatLoading) {
      return;
    }

    setChatError("");
    setIsPortfolioChatLoading(true);
    setPortfolioDraft("");

    setPortfolioMessages((current) => [...current, { role: "user", text: prompt }]);

    try {
      const response = await fetch(`${chatApiBase}/api/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: prompt }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with ${response.status}`);
      }

      const data = await response.json();
      const reply =
        typeof data?.result === "string"
          ? data.result
          : typeof data?.reply === "string"
            ? data.reply
            : "No reply";

      setPortfolioMessages((current) => [...current, { role: "advisor", text: reply }]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Unable to reach the chat service.");
    } finally {
      setIsPortfolioChatLoading(false);
    }
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
        setDataSource("csv");
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
                      {isPortfolioLoading && !holdings.length ? "Loading..." : money(portfolioStats.value)}
                    </div>
                    {lastPriceUpdate === FALLBACK_GENERATED_AT && (
                      <div style={{ color: theme.muted, fontSize: 13, marginTop: 4 }}>
                        Prices as of {new Date(lastPriceUpdate).toLocaleDateString()} — refreshing from server...
                      </div>
                    )}
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
                    <InfoCard label="Tracked holdings" value={`${holdings.length}`} />
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
                      {dataSource === "api"
                        ? `Prices update from server · Last: ${new Date(lastPriceUpdate).toLocaleString()}`
                        : "Viewing your uploaded CSV portfolio locally"}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    {dataSource === "csv" && (
                      <button
                        onClick={() => setDataSource("api")}
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
                        Return to Live Portfolio
                      </button>
                    )}
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
                  {portfolioError && (
                    <div
                      style={{
                        border: `1px solid ${theme.line}`,
                        borderRadius: 20,
                        padding: 16,
                        background: "#fff4f4",
                        color: theme.rose,
                      }}
                    >
                      {portfolioError}
                    </div>
                  )}
                  {isPortfolioLoading && holdings.length === 0 && (
                    <div
                      style={{
                        border: `1px solid ${theme.line}`,
                        borderRadius: 20,
                        padding: 18,
                        background: "#fffdf8",
                        color: theme.muted,
                      }}
                    >
                      Loading holdings from the backend...
                    </div>
                  )}
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
          selectedHolding && (
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
                    label="Day change"
                    value={
                      selectedHolding.dayChangePct === null || selectedHolding.dayChangePct === undefined
                        ? "—"
                        : `${money(selectedHolding.dayChange ?? 0)} (${pct(selectedHolding.dayChangePct)})`
                    }
                  />
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
          )
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
                    <MarkdownMessage text={message.text} />
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
                  disabled={isPortfolioChatLoading}
                  style={{
                    border: "none",
                    background: isPortfolioChatLoading ? "#e6d2b2" : "#f1b04b",
                    color: "#1f2937",
                    borderRadius: 18,
                    padding: "0 18px",
                    cursor: isPortfolioChatLoading ? "not-allowed" : "pointer",
                    fontWeight: 700,
                    opacity: isPortfolioChatLoading ? 0.8 : 1,
                  }}
                >
                  {isPortfolioChatLoading ? "Sending" : "Send"}
                </button>
              </div>
              {(isPortfolioChatLoading || chatError) && (
                <div style={{ marginTop: 8, fontSize: 12, color: chatError ? "#b94b5e" : theme.muted }}>
                  {chatError ? chatError : "Thinking..."}
                </div>
              )}
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
                    <MarkdownMessage text={message.text} />
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
                  disabled={isHoldingChatLoading}
                  style={{
                    border: "none",
                    background: isHoldingChatLoading ? "#e6d2b2" : "#f1b04b",
                    color: "#1f2937",
                    borderRadius: 18,
                    padding: "0 18px",
                    cursor: isHoldingChatLoading ? "not-allowed" : "pointer",
                    fontWeight: 700,
                    opacity: isHoldingChatLoading ? 0.8 : 1,
                  }}
                >
                  {isHoldingChatLoading ? "Sending" : "Send"}
                </button>
              </div>
              {(isHoldingChatLoading || chatError) && (
                <div style={{ marginTop: 8, fontSize: 12, color: chatError ? "#b94b5e" : theme.muted }}>
                  {chatError ? chatError : "Thinking..."}
                </div>
              )}
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

function MarkdownMessage({ text }) {
  return (
    <div
      style={{
        fontSize: 14,
      }}
      dangerouslySetInnerHTML={{ __html: markdownToHtml(text) }}
    />
  );
}

export default App;
