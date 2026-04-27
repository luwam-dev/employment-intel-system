import { ChangeEvent, CSSProperties, useMemo, useState } from "react";

type ManualResult = {
  input_name?: string;
  first_name?: string;
  last_name?: string;
  university?: string;
  matched_name?: string;
  source_url?: string;
  source_title?: string;
  company?: string;
  role?: string;
  location?: string;
  match_status?: string;
  person_match_score?: number | null;
  employment_evidence_score?: number | null;
  final_score?: number | null;
};

type FileRowResult = ManualResult;

type FileResult = {
  type: "file";
  rows_processed?: number;
  matches_found?: number;
  review_count?: number;
  no_match_count?: number;
  output_name?: string;
  download_url?: string;
  rows?: FileRowResult[];
};

type ResultState = ManualResult | FileResult | null;
type ReviewTab = "all" | "matched" | "review" | "no_match";

function isFileResult(result: ResultState): result is FileResult {
  return !!result && "type" in result && result.type === "file";
}

function formatScore(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(4);
}

function safeText(value?: string | null): string {
  return value && value.trim() ? value : "-";
}

export default function App() {
  const [activeTab, setActiveTab] = useState<"upload" | "manual">("upload");
  const [reviewTab, setReviewTab] = useState<ReviewTab>("all");
  const [file, setFile] = useState<File | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [university, setUniversity] = useState("Brunel University London");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ResultState>(null);

  const canSearchManual = useMemo(() => {
    return firstName.trim() !== "" && lastName.trim() !== "";
  }, [firstName, lastName]);

  const filteredRows = useMemo(() => {
    if (!isFileResult(result)) {
      return [];
    }

    const rows = result.rows ?? [];

    if (reviewTab === "matched") {
      return rows.filter((row) => row.match_status === "matched");
    }

    if (reviewTab === "review") {
      return rows.filter((row) => row.match_status === "possible_match");
    }

    if (reviewTab === "no_match") {
      return rows.filter((row) => row.match_status === "no_match");
    }

    return rows;
  }, [result, reviewTab]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
  }

  async function handleUpload() {
    if (!file) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setReviewTab("all");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("university", university);

      const response = await fetch("http://127.0.0.1:8000/api/enrich-xlsx", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("File upload failed.");
      }

      const data: FileResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handleManualSearch() {
    if (!canSearchManual) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/enrich-person", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          university,
        }),
      });

      if (!response.ok) {
        throw new Error("Manual search failed.");
      }

      const data: ManualResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.container}>
        <div style={styles.hero}>
          <div style={styles.badge}>UNIVERSITY PROTOTYPE</div>
          <h1 style={styles.title}>Employment Intel System</h1>
          <p style={styles.subtitle}>
            Upload an Excel file or search for one student manually.
          </p>
        </div>

        <div style={styles.card}>
          <h2 style={styles.sectionTitle}>Search</h2>
          <p style={styles.sectionSubtitle}>Choose manual lookup or batch upload.</p>

          <div style={styles.tabRow}>
            <button
              type="button"
              style={activeTab === "upload" ? styles.activeTab : styles.tab}
              onClick={() => setActiveTab("upload")}
            >
              Upload XLSX
            </button>

            <button
              type="button"
              style={activeTab === "manual" ? styles.activeTab : styles.tab}
              onClick={() => setActiveTab("manual")}
            >
              Manual Search
            </button>
          </div>

          {activeTab === "upload" && (
            <div style={styles.section}>
              <label style={styles.label}>University</label>
              <input
                style={styles.input}
                value={university}
                onChange={(e) => setUniversity(e.target.value)}
                placeholder="Brunel University London"
              />

              <label style={styles.label}>Excel file</label>
              <input
                style={styles.input}
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
              />

              <button
                type="button"
                style={styles.primaryButton}
                onClick={handleUpload}
                disabled={!file || loading}
              >
                {loading ? "Processing..." : "Process file"}
              </button>
            </div>
          )}

          {activeTab === "manual" && (
            <div style={styles.section}>
              <div style={styles.inputGrid}>
                <div>
                  <label style={styles.label}>First name</label>
                  <input
                    style={styles.input}
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="EAMONN"
                  />
                </div>

                <div>
                  <label style={styles.label}>Last name</label>
                  <input
                    style={styles.input}
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="NEMEH"
                  />
                </div>
              </div>

              <label style={styles.label}>University</label>
              <input
                style={styles.input}
                value={university}
                onChange={(e) => setUniversity(e.target.value)}
                placeholder="Brunel University London"
              />

              <button
                type="button"
                style={styles.primaryButton}
                onClick={handleManualSearch}
                disabled={!canSearchManual || loading}
              >
                {loading ? "Searching..." : "Search person"}
              </button>
            </div>
          )}

          {error && <div style={styles.errorBox}>{error}</div>}
        </div>

        <div style={styles.card}>
          <h2 style={styles.sectionTitle}>Results</h2>
          <p style={styles.sectionSubtitle}>Best output returned by the backend pipeline.</p>

          {!result && <p style={styles.emptyText}>No results yet.</p>}

          {result && !isFileResult(result) && (
            <>
              <div style={styles.resultHero}>
                <div>
                  <div style={styles.resultName}>{safeText(result.matched_name || result.input_name)}</div>
                  <div style={styles.resultCompany}>{safeText(result.company)}</div>
                </div>
                <StatusPill value={result.match_status} />
              </div>

              <div style={styles.metricsGrid}>
                <ResultItem label="Company" value={safeText(result.company)} />
                <ResultItem label="Role" value={safeText(result.role)} />
                <ResultItem label="Location" value={safeText(result.location)} />
                <ResultItem label="Person score" value={formatScore(result.person_match_score)} />
                <ResultItem
                  label="Employment score"
                  value={formatScore(result.employment_evidence_score)}
                />
                <ResultItem label="Final score" value={formatScore(result.final_score)} />
                <ResultItem label="Source title" value={safeText(result.source_title)} />
                <ResultItem label="Source URL" value={safeText(result.source_url)} />
              </div>
            </>
          )}

          {result && isFileResult(result) && (
            <>
              <div style={styles.summaryGrid}>
                <SummaryCard label="Rows processed" value={String(result.rows_processed ?? "-")} />
                <SummaryCard label="Matches found" value={String(result.matches_found ?? "-")} />
                <SummaryCard label="Needs review" value={String(result.review_count ?? "-")} />
                <SummaryCard label="No match" value={String(result.no_match_count ?? "-")} />
              </div>

              <div style={styles.actionRow}>
                <div style={styles.filterRow}>
                  <button
                    type="button"
                    style={reviewTab === "all" ? styles.activeSmallTab : styles.smallTab}
                    onClick={() => setReviewTab("all")}
                  >
                    All
                  </button>
                  <button
                    type="button"
                    style={reviewTab === "matched" ? styles.activeSmallTab : styles.smallTab}
                    onClick={() => setReviewTab("matched")}
                  >
                    Matched
                  </button>
                  <button
                    type="button"
                    style={reviewTab === "review" ? styles.activeSmallTab : styles.smallTab}
                    onClick={() => setReviewTab("review")}
                  >
                    Review queue
                  </button>
                  <button
                    type="button"
                    style={reviewTab === "no_match" ? styles.activeSmallTab : styles.smallTab}
                    onClick={() => setReviewTab("no_match")}
                  >
                    No match
                  </button>
                </div>

                <a href={result.download_url || "#"} style={styles.linkButton}>
                  Download enriched file
                </a>
              </div>

              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Input name</th>
                      <th style={styles.th}>Matched name</th>
                      <th style={styles.th}>Company</th>
                      <th style={styles.th}>Role</th>
                      <th style={styles.th}>Location</th>
                      <th style={styles.th}>Status</th>
                      <th style={styles.th}>Final score</th>
                      <th style={styles.th}>Source URL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={styles.emptyTableCell}>
                          No rows in this filter.
                        </td>
                      </tr>
                    ) : (
                      filteredRows.map((row, index) => (
                        <tr key={`${row.input_name || "row"}-${index}`} style={getRowStyle(row.match_status)}>
                          <td style={styles.td}>{safeText(row.input_name)}</td>
                          <td style={styles.td}>{safeText(row.matched_name)}</td>
                          <td style={styles.td}>{safeText(row.company)}</td>
                          <td style={styles.td}>{safeText(row.role)}</td>
                          <td style={styles.td}>{safeText(row.location)}</td>
                          <td style={styles.td}>
                            <StatusPill value={row.match_status} />
                          </td>
                          <td style={styles.td}>{formatScore(row.final_score)}</td>
                          <td style={styles.td}>
                            {row.source_url ? (
                              <a
                                href={row.source_url}
                                target="_blank"
                                rel="noreferrer"
                                style={styles.sourceLink}
                              >
                                Open source
                              </a>
                            ) : (
                              "-"
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ResultItem(props: { label: string; value: string }) {
  return (
    <div style={styles.resultItem}>
      <div style={styles.resultLabel}>{props.label}</div>
      <div style={styles.resultValue}>{props.value}</div>
    </div>
  );
}

function SummaryCard(props: { label: string; value: string }) {
  return (
    <div style={styles.summaryCard}>
      <div style={styles.summaryLabel}>{props.label}</div>
      <div style={styles.summaryValue}>{props.value}</div>
    </div>
  );
}

function StatusPill(props: { value?: string | null }) {
  const value = props.value || "unknown";
  const style =
    value === "matched"
      ? styles.statusMatched
      : value === "possible_match"
      ? styles.statusReview
      : styles.statusNoMatch;

  return <span style={style}>{value}</span>;
}

function getRowStyle(status?: string | null): CSSProperties {
  if (status === "possible_match") {
    return styles.reviewRow;
  }
  if (status === "no_match") {
    return styles.noMatchRow;
  }
  return styles.normalRow;
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: "#eef3ff",
    padding: "32px 16px",
    fontFamily: "Inter, Arial, sans-serif",
    color: "#0f172a",
  },
  container: {
    maxWidth: "1100px",
    margin: "0 auto",
  },
  hero: {
    marginBottom: "20px",
  },
  badge: {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: "999px",
    background: "#dfe4ff",
    color: "#3742c7",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.04em",
    marginBottom: "12px",
  },
  title: {
    margin: 0,
    fontSize: "52px",
    lineHeight: 1.05,
    fontWeight: 800,
    color: "#071a45",
  },
  subtitle: {
    marginTop: "8px",
    marginBottom: 0,
    fontSize: "18px",
    color: "#42526b",
  },
  card: {
    background: "#ffffff",
    border: "1px solid #d9e2f2",
    borderRadius: "18px",
    padding: "18px",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.05)",
    marginBottom: "18px",
  },
  sectionTitle: {
    margin: 0,
    marginBottom: "6px",
    fontSize: "22px",
    fontWeight: 800,
    color: "#071a45",
  },
  sectionSubtitle: {
    margin: 0,
    marginBottom: "16px",
    color: "#51627e",
    fontSize: "14px",
  },
  tabRow: {
    display: "flex",
    gap: "10px",
    marginBottom: "18px",
    flexWrap: "wrap",
  },
  tab: {
    padding: "10px 16px",
    borderRadius: "10px",
    border: "1px solid #c9d4ea",
    background: "#ffffff",
    color: "#071a45",
    cursor: "pointer",
    fontWeight: 700,
  },
  activeTab: {
    padding: "10px 16px",
    borderRadius: "10px",
    border: "1px solid #2d61ff",
    background: "#2d61ff",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 700,
  },
  smallTab: {
    padding: "8px 12px",
    borderRadius: "10px",
    border: "1px solid #c9d4ea",
    background: "#ffffff",
    color: "#071a45",
    cursor: "pointer",
    fontWeight: 700,
    fontSize: "13px",
  },
  activeSmallTab: {
    padding: "8px 12px",
    borderRadius: "10px",
    border: "1px solid #071a45",
    background: "#071a45",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 700,
    fontSize: "13px",
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  inputGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "12px",
  },
  label: {
    display: "block",
    marginBottom: "6px",
    fontWeight: 700,
    color: "#071a45",
    fontSize: "14px",
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: "12px 14px",
    borderRadius: "12px",
    border: "1px solid #c8d4e8",
    fontSize: "14px",
    color: "#071a45",
    background: "#f8fbff",
  },
  primaryButton: {
    marginTop: "4px",
    padding: "14px 18px",
    borderRadius: "12px",
    border: "none",
    background: "#071a45",
    color: "#ffffff",
    cursor: "pointer",
    fontWeight: 800,
    fontSize: "14px",
  },
  errorBox: {
    marginTop: "16px",
    padding: "12px 14px",
    borderRadius: "12px",
    background: "#fff1f2",
    border: "1px solid #fecdd3",
    color: "#be123c",
    fontWeight: 600,
  },
  emptyText: {
    margin: 0,
    color: "#64748b",
  },
  resultHero: {
    display: "flex",
    justifyContent: "space-between",
    gap: "12px",
    alignItems: "flex-start",
    padding: "18px",
    border: "1px solid #d9e2f2",
    borderRadius: "16px",
    background: "#f9fbff",
    marginBottom: "14px",
    flexWrap: "wrap",
  },
  resultName: {
    fontSize: "20px",
    fontWeight: 900,
    color: "#071a45",
    marginBottom: "4px",
  },
  resultCompany: {
    fontSize: "15px",
    color: "#51627e",
    fontWeight: 600,
  },
  metricsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: "12px",
  },
  resultItem: {
    padding: "14px",
    border: "1px solid #d9e2f2",
    borderRadius: "14px",
    background: "#ffffff",
  },
  resultLabel: {
    fontSize: "13px",
    color: "#64748b",
    marginBottom: "8px",
    fontWeight: 600,
  },
  resultValue: {
    fontWeight: 800,
    color: "#071a45",
    wordBreak: "break-word",
    lineHeight: 1.4,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: "12px",
    marginBottom: "14px",
  },
  summaryCard: {
    padding: "14px",
    border: "1px solid #d9e2f2",
    borderRadius: "14px",
    background: "#f9fbff",
  },
  summaryLabel: {
    fontSize: "13px",
    color: "#64748b",
    marginBottom: "8px",
    fontWeight: 700,
  },
  summaryValue: {
    fontSize: "24px",
    fontWeight: 900,
    color: "#071a45",
  },
  actionRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    marginBottom: "14px",
  },
  filterRow: {
    display: "flex",
    gap: "10px",
    flexWrap: "wrap",
  },
  linkButton: {
    display: "inline-block",
    padding: "10px 14px",
    borderRadius: "10px",
    background: "#2d61ff",
    color: "#ffffff",
    textDecoration: "none",
    fontWeight: 800,
  },
  tableWrap: {
    overflowX: "auto",
    border: "1px solid #d9e2f2",
    borderRadius: "14px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "#ffffff",
    minWidth: "900px",
  },
  th: {
    textAlign: "left",
    padding: "12px 14px",
    background: "#f4f7fd",
    color: "#475569",
    fontSize: "13px",
    fontWeight: 800,
    borderBottom: "1px solid #d9e2f2",
  },
  td: {
    padding: "12px 14px",
    borderBottom: "1px solid #edf2f7",
    verticalAlign: "top",
    color: "#0f172a",
    fontSize: "14px",
  },
  emptyTableCell: {
    textAlign: "center",
    padding: "24px",
    color: "#64748b",
  },
  sourceLink: {
    color: "#2563eb",
    textDecoration: "none",
    fontWeight: 700,
  },
  statusMatched: {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: "999px",
    background: "#dcfce7",
    color: "#15803d",
    fontSize: "12px",
    fontWeight: 800,
    textTransform: "lowercase",
  },
  statusReview: {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: "999px",
    background: "#fef3c7",
    color: "#b45309",
    fontSize: "12px",
    fontWeight: 800,
    textTransform: "lowercase",
  },
  statusNoMatch: {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: "999px",
    background: "#e2e8f0",
    color: "#475569",
    fontSize: "12px",
    fontWeight: 800,
    textTransform: "lowercase",
  },
  normalRow: {
    background: "#ffffff",
  },
  reviewRow: {
    background: "#fffbeb",
  },
  noMatchRow: {
    background: "#f8fafc",
  },
};