import { useEffect, useMemo, useState } from "react";

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

function LoadingBar() {
  return (
    <div
      style={{
        marginTop: 10,
        width: "min(420px, 100%)",
        height: 10,
        borderRadius: 999,
        overflow: "hidden",
        background: "rgba(15, 118, 110, 0.12)",
        border: "1px solid rgba(15, 118, 110, 0.18)",
      }}
    >
      <div
        style={{
          width: "42%",
          height: "100%",
          borderRadius: 999,
          background: "linear-gradient(90deg, #0f766e 0%, #57c5b6 58%, #d8f3ef 100%)",
          animation: "portfolioLoadBar 1.2s ease-in-out infinite",
        }}
      />
    </div>
  );
}

function LoadingHoldingCard() {
  return (
    <div
      style={{
        border: `1px solid ${theme.line}`,
        borderRadius: 24,
        padding: 18,
        background: "#fffdf8",
        boxShadow: "0 12px 32px rgba(24, 34, 47, 0.08)",
        display: "grid",
        gridTemplateColumns:
          "minmax(0, 1.1fr) minmax(110px, 0.55fr) repeat(3, minmax(90px, 0.55fr)) minmax(0, 1.5fr)",
        gap: 16,
        alignItems: "center",
      }}
    >
      <div style={{ display: "grid", gap: 10 }}>
        <div style={{ width: 84, height: 14, borderRadius: 999, background: "#efe5d8" }} />
        <div style={{ width: 112, height: 34, borderRadius: 14, background: "#e4d7c4" }} />
      </div>
      <div style={{ width: 88, height: 42, borderRadius: 16, background: "#efe5d8" }} />
      <div style={{ width: 116, height: 42, borderRadius: 16, background: "#efe5d8" }} />
      <div style={{ width: 72, height: 42, borderRadius: 16, background: "#efe5d8" }} />
      <div style={{ width: 92, height: 42, borderRadius: 16, background: "#efe5d8" }} />
      <div style={{ width: "100%", height: 52, borderRadius: 16, background: "#f3ebdf" }} />
    </div>
  );
}

function OverviewMetric({ label, value, tone = "default" }) {
  const stylesByTone = {
    default: {
      background: "#fffdf8",
      border: `1px solid ${theme.line}`,
      valueColor: theme.ink,
      labelColor: theme.muted,
    },
    accent: {
      background: "#dff7f1",
      border: "1px solid rgba(15, 118, 110, 0.15)",
      valueColor: theme.accent,
      labelColor: "#42766f",
    },
    gold: {
      background: "#fff1d9",
      border: "1px solid rgba(183, 121, 31, 0.16)",
      valueColor: theme.gold,
      labelColor: "#8e6a2e",
    },
    rose: {
      background: "#fde6ea",
      border: "1px solid rgba(185, 75, 94, 0.12)",
      valueColor: theme.rose,
      labelColor: "#9a5a68",
    },
  };

  const styles = stylesByTone[tone] ?? stylesByTone.default;

  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: 18,
        background: styles.background,
        border: styles.border,
        minWidth: 120,
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: styles.labelColor }}>
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: 28, fontWeight: 700, lineHeight: 1, color: styles.valueColor }}>
        {value}
      </div>
    </div>
  );
}

function MarketStat({ label, value }) {
  return (
    <div
      style={{
        padding: "14px 16px",
        borderRadius: 18,
        background: "rgba(255, 253, 248, 0.9)",
        border: `1px solid ${theme.line}`,
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: theme.muted }}>
        {label}
      </div>
      <div style={{ marginTop: 8, fontSize: 24, fontWeight: 700, lineHeight: 1.05 }}>{value}</div>
    </div>
  );
}

function HoldingDataCell({ label, value, valueColor, align = "left" }) {
  return (
    <div style={{ textAlign: align }}>
      <div
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: theme.muted,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: valueColor || theme.ink }}>{value}</div>
    </div>
  );
}

const AGENT_FETCH_TIMEOUT_MS = 110000;
const AGENT_RETRY_DELAY_MS = 5000;
const RETRYABLE_STATUS = new Set([502, 503, 504]);

async function fetchAgentReply(apiBase, query, { onWarming } = {}) {
  const endpoint = `${apiBase}/api/agent`;
  const init = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  };

  async function attempt() {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), AGENT_FETCH_TIMEOUT_MS);
    try {
      return await fetch(endpoint, { ...init, signal: controller.signal });
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  let firstResponse;
  let firstError;
  try {
    firstResponse = await attempt();
    if (firstResponse.ok || !RETRYABLE_STATUS.has(firstResponse.status)) {
      return firstResponse;
    }
  } catch (error) {
    firstError = error;
  }

  if (onWarming) onWarming();
  await new Promise((resolve) => window.setTimeout(resolve, AGENT_RETRY_DELAY_MS));

  try {
    return await attempt();
  } catch (retryError) {
    throw firstError ?? retryError;
  }
}

function App() {
  const [holdings, setHoldings] = useState([]);
  const [cashBalances, setCashBalances] = useState([]);
  const [lastPriceUpdate, setLastPriceUpdate] = useState("");
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
    const equitiesValue = holdings.reduce((sum, holding) => sum + holding.shares * holding.price, 0);
    const cost = holdings.reduce((sum, holding) => sum + holding.shares * holding.avgCost, 0);
    const cash = cashBalances.reduce((sum, balance) => sum + balance.cashBalance, 0);
    const largestHolding = holdings.reduce(
      (largest, holding) =>
        !largest || holding.shares * holding.price > largest.shares * largest.price ? holding : largest,
      null,
    );
    const value = equitiesValue + cash;
    const pnl = value - cost - cash;
    return {
      value,
      equitiesValue,
      cash,
      pnl,
      pnlPct: cost ? (pnl / cost) * 100 : 0,
      cost,
      largestHolding,
    };
  }, [cashBalances, holdings]);

  const currentMessages = selectedHolding ? messagesBySymbol[selectedHolding.symbol] ?? [] : [];
  const equitySharePct = portfolioStats.value > 0 ? (portfolioStats.equitiesValue / portfolioStats.value) * 100 : 0;
  const cashSharePct = portfolioStats.value > 0 ? (portfolioStats.cash / portfolioStats.value) * 100 : 0;

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
    let isDisposed = false;

    async function loadPortfolio() {
      setPortfolioError("");
      setIsPortfolioLoading(true);

      try {
        const portfolioResponse = await fetch(`${chatApiBase}/api/portfolio`);

        if (!portfolioResponse.ok) {
          throw new Error(`Portfolio request failed with ${portfolioResponse.status}`);
        }

        const portfolioData = await portfolioResponse.json();
        const nextHoldings = Array.isArray(portfolioData?.holdings) ? portfolioData.holdings : [];
        const nextCashBalances = Array.isArray(portfolioData?.cashBalances) ? portfolioData.cashBalances : [];

        if (!nextHoldings.length) {
          throw new Error("Portfolio API returned no holdings.");
        }

        if (!isDisposed) {
          setHoldings(nextHoldings);
          setCashBalances(nextCashBalances);
          setLastPriceUpdate(
            typeof portfolioData?.latestTradingDate === "string"
              ? `${portfolioData.latestTradingDate}T00:00:00Z`
              : new Date().toISOString(),
          );
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
  }, [chatApiBase]);

  useEffect(() => {
    if (!isPortfolioChatExpanded && !isHoldingChatExpanded) return;
    fetch(`${chatApiBase}/api/health`, { method: "GET" }).catch(() => {});
  }, [chatApiBase, isPortfolioChatExpanded, isHoldingChatExpanded]);

  async function openHolding(symbol) {
    setSelectedSymbol(symbol);
    setView("holding");

    try {
      const response = await fetch(`${chatApiBase}/api/stock-prices/latest/${symbol}`);

      if (!response.ok) {
        throw new Error(`Holding request failed with ${response.status}`);
      }

      const latestHoldingPrice = await response.json();
      setHoldings((current) =>
        current.map((holding) =>
          holding.symbol === symbol
            ? {
                ...holding,
                price: typeof latestHoldingPrice.price === "number" ? latestHoldingPrice.price : holding.price,
                currency: latestHoldingPrice.currency || holding.currency || "USD",
                tradingDate: latestHoldingPrice.tradingDate || holding.tradingDate,
                dayChange: null,
                dayChangePct: null,
              }
            : holding,
        ),
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
      const response = await fetchAgentReply(chatApiBase, prompt, {
        onWarming: () => setChatError("Backend is waking up, retrying in a few seconds..."),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        const message =
          typeof detail?.detail === "string"
            ? detail.detail
            : `Request failed with ${response.status}`;
        throw new Error(message);
      }

      setChatError("");
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
      const reason =
        error?.name === "AbortError"
          ? "The chat service took too long to respond. Try a shorter question or retry in a minute."
          : error instanceof Error
            ? error.message
            : "Unable to reach the chat service.";
      setChatError(reason);
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
      const response = await fetchAgentReply(chatApiBase, prompt, {
        onWarming: () => setChatError("Backend is waking up, retrying in a few seconds..."),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        const message =
          typeof detail?.detail === "string"
            ? detail.detail
            : `Request failed with ${response.status}`;
        throw new Error(message);
      }

      setChatError("");
      const data = await response.json();
      const reply =
        typeof data?.result === "string"
          ? data.result
          : typeof data?.reply === "string"
            ? data.reply
            : "No reply";

      setPortfolioMessages((current) => [...current, { role: "advisor", text: reply }]);
    } catch (error) {
      const reason =
        error?.name === "AbortError"
          ? "The chat service took too long to respond. Try a shorter question or retry in a minute."
          : error instanceof Error
            ? error.message
            : "Unable to reach the chat service.";
      setChatError(reason);
    } finally {
      setIsPortfolioChatLoading(false);
    }
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
          maxWidth: 1180,
          margin: "0 auto",
          padding: "24px 18px 164px",
        }}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 18,
            marginBottom: 22,
            padding: "12px 16px",
            borderRadius: 999,
            background: "rgba(255, 250, 243, 0.92)",
            border: `1px solid ${theme.line}`,
            boxShadow: "0 16px 34px rgba(24, 34, 47, 0.08)",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 42,
                height: 42,
                borderRadius: 999,
                background: "linear-gradient(135deg, #18222f, #314658)",
                border: `1px solid ${theme.line}`,
                color: "#fffdf8",
                fontSize: 18,
                fontWeight: 700,
              }}
            >
              M
            </div>
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: theme.muted,
                  marginBottom: 2,
                }}
              >
                Meridian
              </div>
              <div
                style={{
                  fontSize: 28,
                  lineHeight: 1,
                  fontFamily: fonts.display,
                  fontWeight: 700,
                  letterSpacing: "-0.04em",
                  whiteSpace: "nowrap",
                }}
              >
                Portfolio
              </div>
            </div>
          </div>
          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
            }}
            aria-label="Global navigation"
          >
            {[
              { label: "Portfolio", active: true },
              { label: "Analytics", active: false },
              { label: "Cash", active: false },
              { label: "Settings", active: false },
            ].map((item) => (
              <button
                key={item.label}
                type="button"
                style={{
                  border: item.active ? `1px solid rgba(15, 118, 110, 0.18)` : `1px solid ${theme.line}`,
                  background: item.active ? "rgba(216, 243, 239, 0.92)" : "#fffdf8",
                  color: item.active ? theme.accent : theme.ink,
                  borderRadius: 999,
                  padding: "10px 14px",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: item.active ? "default" : "pointer",
                  boxShadow: item.active ? "0 10px 20px rgba(15, 118, 110, 0.08)" : "none",
                }}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
              justifyContent: "flex-end",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 12px",
                borderRadius: 999,
                background: "rgba(216, 243, 239, 0.92)",
                border: "1px solid rgba(15, 118, 110, 0.14)",
                color: theme.accent,
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: theme.accent,
                }}
              />
              Live data
            </div>
            <div
              style={{
                padding: "9px 12px",
                borderRadius: 999,
                background: "#fffdf8",
                border: `1px solid ${theme.line}`,
                fontSize: 13,
                color: theme.muted,
              }}
            >
              {lastPriceUpdate ? new Date(lastPriceUpdate).toLocaleDateString() : "Syncing"}
            </div>
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
                  padding: 20,
                  boxShadow: theme.shadow,
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(0, 1.15fr) minmax(320px, 0.85fr)",
                    gap: 22,
                    alignItems: "stretch",
                  }}
                >
                  <div
                    style={{
                      display: "grid",
                      gridTemplateRows: "auto auto 1fr",
                      gap: 16,
                    }}
                  >
                    <div>
                      <div
                        style={{
                          color: theme.muted,
                          marginBottom: 10,
                          fontSize: 12,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                        }}
                      >
                        Portfolio overview
                      </div>
                      <div style={{ fontSize: "clamp(2.4rem, 5vw, 4.5rem)", fontWeight: 700, lineHeight: 0.95 }}>
                        {isPortfolioLoading && !holdings.length ? "Loading..." : money(portfolioStats.value)}
                      </div>
                      <div style={{ color: theme.muted, fontSize: 15, marginTop: 10, maxWidth: 520, lineHeight: 1.5 }}>
                        A live snapshot of equity exposure, available cash, and the latest pricing date from the
                        portfolio database.
                      </div>
                    </div>
                    {!lastPriceUpdate && isPortfolioLoading && (
                      <>
                        <div style={{ color: theme.muted, fontSize: 13, marginTop: 4 }}>
                          Loading latest portfolio data from the server...
                        </div>
                        <LoadingBar />
                      </>
                    )}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(2, minmax(160px, 1fr))",
                        gap: 12,
                      }}
                    >
                      <OverviewMetric label="Unrealized P/L" value={money(portfolioStats.pnl)} tone="accent" />
                      <OverviewMetric label="Portfolio Return" value={pct(portfolioStats.pnlPct)} tone="gold" />
                      <OverviewMetric label="Cash Reserve" value={money(portfolioStats.cash)} tone="rose" />
                      <OverviewMetric label="Tracked Holdings" value={`${holdings.length}`} />
                    </div>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateRows: "auto auto",
                      gap: 14,
                      padding: 18,
                      borderRadius: 24,
                      background: "linear-gradient(180deg, rgba(255,253,248,0.94), rgba(244,239,231,0.94))",
                      border: `1px solid ${theme.line}`,
                    }}
                  >
                    <div>
                      <div
                        style={{
                          color: theme.muted,
                          fontSize: 12,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                          marginBottom: 12,
                        }}
                      >
                        Market state
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                        <MarketStat label="Largest position" value={portfolioStats.largestHolding?.symbol ?? "—"} />
                        <MarketStat label="Cost basis" value={money(portfolioStats.cost)} />
                        <MarketStat label="Equity value" value={money(portfolioStats.equitiesValue)} />
                        <MarketStat
                          label="Latest pricing date"
                          value={lastPriceUpdate ? new Date(lastPriceUpdate).toLocaleDateString() : "—"}
                        />
                      </div>
                    </div>
                    <div
                      style={{
                        borderRadius: 20,
                        padding: 14,
                        background: "rgba(255, 250, 243, 0.9)",
                        border: `1px solid ${theme.line}`,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
                        <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: theme.muted }}>
                          Capital mix
                        </div>
                        <div style={{ color: theme.muted, fontSize: 13 }}>
                          {equitySharePct.toFixed(0)}% equities / {cashSharePct.toFixed(0)}% cash
                        </div>
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: `${Math.max(equitySharePct, 8)}fr ${Math.max(cashSharePct, 8)}fr`,
                          gap: 8,
                          height: 18,
                        }}
                      >
                        <div
                          style={{
                            borderRadius: 999,
                            background: "linear-gradient(90deg, #18222f 0%, #314658 100%)",
                          }}
                        />
                        <div
                          style={{
                            borderRadius: 999,
                            background: "linear-gradient(90deg, #f1b8c3 0%, #b94b5e 100%)",
                          }}
                        />
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginTop: 12 }}>
                        <div>
                          <div style={{ fontSize: 12, color: theme.muted }}>Equities</div>
                          <div style={{ fontSize: 20, fontWeight: 700 }}>{money(portfolioStats.equitiesValue)}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <div style={{ fontSize: 12, color: theme.muted }}>Cash</div>
                          <div style={{ fontSize: 20, fontWeight: 700 }}>{money(portfolioStats.cash)}</div>
                        </div>
                      </div>
                    </div>
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
                  background: "rgba(255, 250, 243, 0.82)",
                  border: `1px solid ${theme.line}`,
                  borderRadius: 28,
                  padding: 18,
                  boxShadow: "0 18px 38px rgba(24, 34, 47, 0.07)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 14,
                    flexWrap: "wrap",
                  }}
                >
                  <div>
                    <h2 style={{ fontSize: 24, marginBottom: 4 }}>Holdings</h2>
                    <div style={{ color: theme.muted, fontSize: 14 }}>
                      {lastPriceUpdate
                        ? `Prices update from server · Last: ${new Date(lastPriceUpdate).toLocaleString()}`
                        : "Loading latest prices from server"}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <div
                      style={{
                        padding: "9px 12px",
                        borderRadius: 999,
                        background: "#fffdf8",
                        border: `1px solid ${theme.line}`,
                        fontSize: 13,
                        color: theme.muted,
                      }}
                    >
                      {holdings.length} positions
                    </div>
                    <div
                      style={{
                        padding: "9px 12px",
                        borderRadius: 999,
                        background: "rgba(216, 243, 239, 0.92)",
                        border: "1px solid rgba(15, 118, 110, 0.14)",
                        fontSize: 13,
                        color: theme.accent,
                        fontWeight: 600,
                      }}
                    >
                      Click any row for details
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
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
                    <>
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
                      <LoadingHoldingCard />
                      <LoadingHoldingCard />
                      <LoadingHoldingCard />
                    </>
                  )}
                  {holdings.length > 0 && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "minmax(0, 1.15fr) repeat(5, minmax(92px, 0.56fr)) 28px",
                        gap: 14,
                        alignItems: "center",
                        padding: "0 18px 4px",
                        color: theme.muted,
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                      }}
                    >
                      <div>Holding</div>
                      <div style={{ textAlign: "right" }}>Weight</div>
                      <div style={{ textAlign: "right" }}>Return</div>
                      <div style={{ textAlign: "right" }}>Market value</div>
                      <div style={{ textAlign: "right" }}>Shares</div>
                      <div style={{ textAlign: "right" }}>Avg cost</div>
                      <div />
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
                          borderRadius: 22,
                          padding: "16px 18px",
                          background: "#fffdf8",
                          cursor: "pointer",
                          boxShadow: "0 12px 32px rgba(24, 34, 47, 0.08)",
                          display: "grid",
                          gridTemplateColumns: "minmax(0, 1.15fr) repeat(5, minmax(92px, 0.56fr)) 28px",
                          gap: 14,
                          alignItems: "center",
                          transition: "transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 14,
                          }}
                        >
                          <div>
                            <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{holding.symbol}</div>
                            <div style={{ fontSize: 13, color: theme.muted, marginTop: 4 }}>{holding.name}</div>
                          </div>
                        </div>

                        <HoldingDataCell
                          label="Weight"
                          value={`${((marketValue / portfolioStats.value) * 100).toFixed(1)}%`}
                          align="right"
                        />
                        <HoldingDataCell
                          label="Return"
                          value={pct(gainPct)}
                          valueColor={gainPct >= 0 ? theme.accent : theme.rose}
                          align="right"
                        />
                        <HoldingDataCell label="Market value" value={money(marketValue)} align="right" />
                        <HoldingDataCell label="Shares" value={`${holding.shares}`} align="right" />
                        <HoldingDataCell label="Avg cost" value={money(holding.avgCost)} align="right" />
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "flex-end",
                            color: theme.muted,
                            fontSize: 22,
                          }}
                        >
                          ›
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
                  padding: 20,
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

                {Array.isArray(selectedHolding.notes) && selectedHolding.notes.length > 0 && (
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
                )}
              </div>
            </section>
          )
        )}
      </div>
      <style>{`
        @keyframes portfolioLoadBar {
          0% {
            transform: translateX(-112%) scaleX(0.86);
          }
          55% {
            transform: translateX(148%) scaleX(1.04);
          }
          100% {
            transform: translateX(258%) scaleX(0.86);
          }
        }
      `}</style>
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
                {["What is the risk?", "Should I trim?", "Should I add more?", "How large is this position?"].map(
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
