import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { motion } from "framer-motion";
import {
  ShieldAlert, Download, Target, ChevronRight, Activity, Wrench,
  Globe, Figma, FileText, Copy, AlertTriangle, Sparkles, Monitor,
  Smartphone, Camera, ChevronDown, Server, Terminal, Lock, Loader2,
  TriangleAlert, DatabaseZap, ShieldX, Layers, Accessibility, KeyRound,
  ExternalLink, Bug, MousePointerClick,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useScan } from "@/context/scan-context";
import { getReportUrl } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

/* ── Severity colours (Google dark theme) ── */
const SEV_CLASSES: Record<string, string> = {
  critical: "bg-[#f28b82]/12 text-[#f28b82] border-[#f28b82]/25",
  serious:  "bg-[#fdd663]/10 text-[#fdd663] border-[#fdd663]/25",
  moderate: "bg-[#fdd663]/8 text-[#fdd663]/80 border-[#fdd663]/20",
  minor:    "bg-[#81c995]/10 text-[#81c995] border-[#81c995]/25",
};

const VIEWPORT_ICON: Record<string, any> = {
  desktop: Monitor,
  mobile:  Smartphone,
};

const BACKEND_CATEGORIES = new Set([
  "ERROR_STATE", "BROKEN_API", "AUTH_FAILURE", "LOADING_STUCK",
  "FORM_BROKEN", "CONSOLE_ERROR_VISIBLE", "MISSING_CONTENT", "API_DATA_STALE",
]);

const BACKEND_CAT_ICON: Record<string, any> = {
  ERROR_STATE:            TriangleAlert,
  BROKEN_API:             DatabaseZap,
  AUTH_FAILURE:           Lock,
  LOADING_STUCK:          Loader2,
  FORM_BROKEN:            Layers,
  CONSOLE_ERROR_VISIBLE:  Terminal,
  MISSING_CONTENT:        ShieldX,
  API_DATA_STALE:         Activity,
};

const NETWORK_TYPE_ICON: Record<string, any> = {
  api_error:          Server,
  slow_api:           Activity,
  cors_error:         ShieldX,
  js_error:           Terminal,
  uncaught_exception: TriangleAlert,
};

const NETWORK_TYPE_LABEL: Record<string, string> = {
  api_error:          "API Error",
  slow_api:           "Slow Request",
  cors_error:         "CORS Error",
  js_error:           "JS Console Error",
  uncaught_exception: "Uncaught Exception",
};

function SevBadge({ severity }: { severity: string }) {
  return (
    <Badge variant="outline" className={`${SEV_CLASSES[severity?.toLowerCase()] ?? SEV_CLASSES.moderate} capitalize font-semibold text-xs`}>
      {severity}
    </Badge>
  );
}

function CopyBtn({ text }: { text: string }) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        toast({ title: "Copied to clipboard" });
        setTimeout(() => setCopied(false), 2000);
      }}
      className="text-muted-foreground hover:text-primary transition-colors p-1 rounded"
      title="Copy"
    >
      <Copy className="w-3.5 h-3.5" />
      {copied && <span className="sr-only">Copied</span>}
    </button>
  );
}

type Tab = "bugs" | "functional" | "backend" | "a11y" | "security" | "design";

export default function ResultsPage() {
  const [, setLocation] = useLocation();
  const { currentScan } = useScan();
  const [tab, setTab] = useState<Tab>("bugs");
  const [showPages, setShowPages] = useState(false);

  useEffect(() => {
    if (!currentScan) setLocation("/");
  }, [currentScan, setLocation]);

  if (!currentScan) return null;

  const {
    allBugs = [], networkIssues = [], figmaDeviations = [],
    fixes = [], newBugs = [], performanceMetrics = {},
    qualityScore, figmaMatchScore, pagesVisited = [], screenshotsMeta = [],
    domA11yBugs = [], securityBugs = [], functionalBugs = [],
    designInconsistencies = [], designConsistencyScore,
    healingEvents = [],
  } = currentScan;

  const frontendBugs          = allBugs.filter(b => !BACKEND_CATEGORIES.has(b.category));
  const backendBugsFromGemini = allBugs.filter(b => BACKEND_CATEGORIES.has(b.category));
  const allBackendIssues      = [
    ...backendBugsFromGemini.map(b  => ({ _type: "gemini",  ...b })),
    ...networkIssues.map(n          => ({ _type: "network", ...n })),
  ];

  const critical   = allBugs.filter(b => b.severity?.toLowerCase() === "critical").length;
  const serious    = allBugs.filter(b => b.severity?.toLowerCase() === "serious").length;

  const scoreColor = qualityScore >= 80 ? "text-[#81c995]"
    : qualityScore >= 60 ? "text-[#fdd663]" : "text-[#f28b82]";
  const scoreBg    = qualityScore >= 80 ? "border-[#81c995]/25 bg-[#81c995]/8"
    : qualityScore >= 60 ? "border-[#fdd663]/25 bg-[#fdd663]/8" : "border-[#f28b82]/25 bg-[#f28b82]/8";

  const jsErrCount   = (performanceMetrics as any).jsErrorCount   || 0;
  const corsErrCount = (performanceMetrics as any).corsErrorCount || 0;

  const tabs: { id: Tab; label: string; count: number; icon: any }[] = [
    { id: "bugs",       label: "Visual Bugs",      count: frontendBugs.length,          icon: ShieldAlert },
    { id: "functional", label: "Functional QA",    count: functionalBugs.length,        icon: MousePointerClick },
    { id: "backend",    label: "Backend & API",    count: allBackendIssues.length,      icon: Server },
    { id: "a11y",       label: "Accessibility",    count: domA11yBugs.length,           icon: Accessibility },
    { id: "security",   label: "Security",         count: securityBugs.length,          icon: KeyRound },
    { id: "design",     label: "Design Intelligence", count: figmaDeviations.length + designInconsistencies.length, icon: Figma },
  ];

  return (
    <div className="min-h-[calc(100vh-4.5rem)]">
      {/* ── Page header ── */}
      <div className="page-glass-header px-6 lg:px-12 py-7">
        <div className="max-w-screen-xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-5">
          <div>
            <span className="section-label block mb-2">QA Report</span>
            <h1 className="text-2xl font-display font-bold text-white">Scan Results</h1>
            <div className="flex items-center gap-2 mt-1.5 text-sm text-white/50">
              <Target className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate max-w-md">{currentScan.url}</span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5 text-xs text-white/40">
              <Globe className="w-3 h-3" />
              {pagesVisited.length} pages scanned
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              className="border-white/30 text-white bg-white/8 hover:bg-white/15 hover:border-white/50"
              onClick={() => window.open(getReportUrl(currentScan.scanId), "_blank")}
            >
              <FileText className="w-4 h-4 mr-2" /> Download PDF
            </Button>
            <Button
              size="sm"
              className="bg-gradient-primary text-white shadow-sm hover:opacity-90"
              onClick={() => setLocation("/fix-executor")}
            >
              Fix Executor <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-screen-xl mx-auto px-6 lg:px-12 py-8 space-y-8">

        {/* ── KPI cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {/* Quality score */}
          <div className={`rounded-xl border p-6 ${scoreBg}`}>
            <p className="section-label mb-2">Quality Score</p>
            <p className={`text-5xl font-medium ${scoreColor}`}>{qualityScore}</p>
            <p className="text-xs text-white/35 mt-1">out of 100</p>
          </div>

          {/* Frontend bugs */}
          <div className="rounded-xl border border-white/8 p-6" style={{ background: "#1e1f20" }}>
            <p className="section-label mb-2">Frontend Bugs</p>
            <p className="text-5xl font-medium text-white">{frontendBugs.length}</p>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              <span className="pill bg-[#f28b82]/12 text-[#f28b82] border border-[#f28b82]/25">{critical} critical</span>
              <span className="pill bg-[#fdd663]/10 text-[#fdd663] border border-[#fdd663]/25">{serious} serious</span>
            </div>
          </div>

          {/* Backend / API */}
          <div className="rounded-xl border border-white/8 p-6" style={{ background: "#1e1f20" }}>
            <p className="section-label mb-2">Backend & API</p>
            <p className="text-5xl font-medium text-white">{allBackendIssues.length}</p>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {networkIssues.length > 0 && (
                <span className="pill bg-[#fdd663]/10 text-[#fdd663] border border-[#fdd663]/25">{networkIssues.length} network</span>
              )}
              {backendBugsFromGemini.length > 0 && (
                <span className="pill bg-[#f28b82]/12 text-[#f28b82] border border-[#f28b82]/25">{backendBugsFromGemini.length} UI errors</span>
              )}
            </div>
          </div>

          {/* A11y / Security */}
          <div className="rounded-xl border border-white/8 p-6" style={{ background: "#1e1f20" }}>
            <p className="section-label mb-2">Accessibility</p>
            <p className="text-5xl font-medium text-white">{domA11yBugs.length}</p>
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {securityBugs.length > 0 && (
                <span className="pill bg-[#fdd663]/10 text-[#fdd663] border border-[#fdd663]/25">{securityBugs.length} security</span>
              )}
              {newBugs.length > 0 && (
                <span className="pill bg-white/8 text-white/40 border border-white/10">{newBugs.length} new</span>
              )}
            </div>
          </div>

          {/* Design consistency */}
          {typeof designConsistencyScore === "number" && (
            <div className="rounded-xl border border-white/8 p-6" style={{ background: "#1e1f20" }}>
              <p className="section-label mb-2">Design Consistency</p>
              <p className={`text-5xl font-medium ${designConsistencyScore >= 80 ? "text-[#81c995]" : designConsistencyScore >= 60 ? "text-[#fdd663]" : "text-[#f28b82]"}`}>
                {designConsistencyScore}
              </p>
              <div className="flex gap-1.5 mt-2 flex-wrap">
                <span className="pill bg-white/8 text-white/40 border border-white/10">
                  {designInconsistencies.length} token drift{designInconsistencies.length === 1 ? "" : "s"}
                </span>
                {healingEvents.length > 0 && (
                  <span className="pill bg-[#8ab4f8]/10 text-[#8ab4f8] border border-[#8ab4f8]/25">
                    {healingEvents.length} self-healed
                  </span>
                )}
              </div>
            </div>
          )}
        </motion.div>

        {/* ── Perf strip ── */}
        {(performanceMetrics as any).initialLoadMs && (
          <div className="flex flex-wrap gap-6 px-6 py-4 rounded-xl border border-white/8 text-sm text-white/40 font-normal" style={{ background: "#1e1f20" }}>
            <span><b className="text-white font-medium">{(performanceMetrics as any).initialLoadMs}ms</b> load</span>
            <span><b className="text-white font-medium">{pagesVisited.length}</b> pages</span>
            <span><b className="text-white font-medium">{(performanceMetrics as any).totalRequests}</b> requests</span>
            {((performanceMetrics as any).errorCount || 0) > 0 && (
              <span style={{ color: "#f28b82" }}><b>{(performanceMetrics as any).errorCount}</b> API errors</span>
            )}
            {((performanceMetrics as any).slowRequestCount || 0) > 0 && (
              <span style={{ color: "#fdd663" }}><b>{(performanceMetrics as any).slowRequestCount}</b> slow</span>
            )}
            {jsErrCount > 0 && (
              <span style={{ color: "#fdd663" }}><b>{jsErrCount}</b> JS errors</span>
            )}
            {corsErrCount > 0 && (
              <span style={{ color: "#f28b82" }}><b>{corsErrCount}</b> CORS</span>
            )}
          </div>
        )}

        {/* ── Screenshots ── */}
        {screenshotsMeta.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setShowPages(v => !v)}
              className="flex items-center gap-2 text-sm text-white/40 hover:text-white/70 transition-colors"
            >
              <Camera className="w-4 h-4" style={{ color: "#8ab4f8" }} />
              <span>
                <b className="text-white">{screenshotsMeta.length}</b> screenshots across{" "}
                <b className="text-white">{pagesVisited.length}</b> pages
              </span>
              <ChevronDown className={`w-4 h-4 transition-transform ${showPages ? "rotate-180" : ""}`} />
            </button>
            {showPages && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 pt-1"
              >
                {screenshotsMeta.map((s: any, i: number) => {
                  const VpIcon = VIEWPORT_ICON[s.viewport || "desktop"] || Monitor;
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-2 text-xs rounded-lg px-3 py-2 border border-white/8"
                      style={{ background: "#1e1f20" }}
                    >
                      <VpIcon className="w-3.5 h-3.5 shrink-0" style={{ color: "#8ab4f8" }} />
                      <span className="truncate text-white/45">{s.label}</span>
                    </div>
                  );
                })}
              </motion.div>
            )}
          </div>
        )}

        {/* ── New bugs banner ── */}
        {newBugs.length > 0 && (
          <div className="flex items-center gap-3 p-4 rounded-xl border border-[#fdd663]/25" style={{ background: "rgba(253,214,99,0.08)" }}>
            <Sparkles className="w-5 h-5 shrink-0" style={{ color: "#fdd663" }} />
            <span className="text-sm" style={{ color: "#fdd663" }}>
              <b>{newBugs.length} new bugs</b> detected since your last scan of this URL.
            </span>
          </div>
        )}

        {/* ── Tabs ── */}
        <div className="flex gap-1 border-b border-white/8">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-all border-b-2 -mb-px ${
                tab === t.id
                  ? "border-[#8ab4f8] text-[#8ab4f8]"
                  : "border-transparent text-white/35 hover:text-white/65"
              }`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
              {t.count > 0 && (
                <span className={`inline-flex items-center justify-center rounded-full text-[11px] font-bold px-1.5 min-w-[1.25rem] h-5 ${
                  tab === t.id
                    ? "bg-[#8ab4f8]/12 text-[#8ab4f8]"
                    : t.id === "backend" && t.count > 0
                      ? "bg-[#f28b82]/12 text-[#f28b82]"
                      : "bg-white/8 text-white/40"
                }`}>
                  {t.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── FRONTEND BUGS ── */}
        {tab === "bugs" && (
          <div className="space-y-3">
            {frontendBugs.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <ShieldAlert className="w-12 h-12 mx-auto mb-3 opacity-20" />
                No frontend visual bugs detected.
              </div>
            ) : (
              frontendBugs.map((bug, idx) => {
                const VpIcon = VIEWPORT_ICON[bug.viewport || "desktop"] || Monitor;
                const fix    = fixes.find((f: any) => f.bugId === bug.bugId);
                return (
                  <motion.div
                    key={`${bug.bugId}-${idx}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className="rounded-xl overflow-hidden border border-white/8 hover:border-white/15 transition-all"
                    style={{ background: "#1e1f20" }}
                  >
                    <div className="p-5 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <SevBadge severity={bug.severity} />
                        <Badge variant="secondary" className="font-mono text-xs bg-white/8 text-white/65 border-white/10">
                          {bug.category}
                        </Badge>
                        <Badge variant="outline" className="text-white/40 text-xs flex items-center gap-1 border-white/12">
                          <VpIcon className="w-3 h-3" />{bug.viewport}
                        </Badge>
                        {bug.label && <span className="text-xs text-white/35">{bug.label}</span>}
                      </div>
                      <p className="text-sm text-white/80 leading-relaxed">{bug.description}</p>
                      <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8" style={{ background: "rgba(255,255,255,0.03)" }}>
                        {bug.elementDescription || bug.element || "Element not specified"}
                      </p>
                      {(fix?.devtoolsCommand || bug.devtoolsCommand) && (
                        <div className="rounded-lg p-3 border border-[#34A853]/20" style={{ background: "rgba(52,168,83,0.07)" }}>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium flex items-center gap-1" style={{ color: "#81c995" }}>
                              <Wrench className="w-3 h-3" /> DevTools Fix
                            </span>
                            <CopyBtn text={fix?.devtoolsCommand || bug.devtoolsCommand || ""} />
                          </div>
                          <code className="text-xs font-mono break-all" style={{ color: "#81c995" }}>
                            {fix?.devtoolsCommand || bug.devtoolsCommand}
                          </code>
                        </div>
                      )}
                      {(fix?.cssFix || bug.cssfix) && (
                        <div className="rounded-lg p-3 border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.07)" }}>
                          <span className="text-xs font-medium" style={{ color: "#8ab4f8" }}>CSS: </span>
                          <code className="text-xs font-mono" style={{ color: "#8ab4f8" }}>{fix?.cssFix || bug.cssfix}</code>
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        )}

        {/* ── FUNCTIONAL QA ── */}
        {tab === "functional" && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-4 rounded-xl border border-[#4285F4]/20" style={{ background: "rgba(66,133,244,0.05)" }}>
              <MousePointerClick className="w-5 h-5 shrink-0" style={{ color: "#4285F4" }} />
              <span className="text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>
                Agentic Playwright interactions — testing form submissions, button clicks, and UI state changes dynamically.
              </span>
            </div>
            {healingEvents.length > 0 && (
              <div className="flex items-start gap-3 p-4 rounded-xl border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.05)" }}>
                <span className="text-lg leading-none">🩹</span>
                <div className="space-y-1.5">
                  <span className="text-sm font-medium" style={{ color: "#8ab4f8" }}>
                    {healingEvents.length} element{healingEvents.length === 1 ? "" : "s"} self-healed this scan
                  </span>
                  {healingEvents.map((event: any, idx: number) => (
                    <p key={idx} className="text-xs text-white/50 leading-relaxed">
                      <span className="font-mono text-white/70">{event.label}</span> couldn't be found via{" "}
                      <span className="font-mono">{event.originalStrategy}</span> — recovered via{" "}
                      <span className="font-mono" style={{ color: "#8ab4f8" }}>{event.healedStrategy}</span> match.
                    </p>
                  ))}
                </div>
              </div>
            )}
            {functionalBugs.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <MousePointerClick className="w-12 h-12 mx-auto mb-3 opacity-20" />
                No functional interaction bugs detected! Forms and buttons worked successfully.
              </div>
            ) : (
              functionalBugs.map((bug: any, idx: number) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.02 }}
                  className="rounded-xl overflow-hidden border border-white/8 hover:border-white/15 transition-all"
                  style={{ background: "#1e1f20" }}
                >
                  <div className="p-5 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SevBadge severity={bug.severity} />
                      <Badge variant="secondary" className="font-mono text-xs bg-white/8 text-white/65 border-white/10">
                        {bug.category?.replace(/_/g, " ")}
                      </Badge>
                      <Badge variant="outline" className="text-xs border-[#4285F4]/25" style={{ color: "#4285F4", background: "rgba(66,133,244,0.06)" }}>
                        <MousePointerClick className="w-3 h-3 mr-1" /> Agent Action
                      </Badge>
                      {bug.healed && (
                        <Badge variant="outline" className="text-xs border-[#8ab4f8]/25" style={{ color: "#8ab4f8", background: "rgba(138,180,248,0.06)" }}>
                          🩹 Self-healed
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-white/80 leading-relaxed font-semibold">{bug.actionAttempted}</p>
                    <p className="text-sm text-white/60 leading-relaxed">{bug.description}</p>
                    {bug.elementSelector && (
                      <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8" style={{ background: "rgba(255,255,255,0.03)" }}>
                        Selector: {bug.elementSelector}
                      </p>
                    )}
                    {bug.url && (
                      <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8 truncate" style={{ background: "rgba(255,255,255,0.03)" }}>
                        {bug.url}
                      </p>
                    )}
                  </div>
                </motion.div>
              ))
            )}
          </div>
        )}

        {/* ── BACKEND & API ── */}
        {tab === "backend" && (
          <div className="space-y-3">
            {allBackendIssues.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <Server className="w-12 h-12 mx-auto mb-3 opacity-20" />
                No backend or API issues detected.
              </div>
            ) : (
              allBackendIssues.map((issue: any, idx) => {
                const isGemini  = issue._type === "gemini";
                const TypeIcon  = isGemini
                  ? (BACKEND_CAT_ICON[issue.category] || Server)
                  : (NETWORK_TYPE_ICON[issue.type] || Server);
                const typeLabel = isGemini
                  ? issue.category?.replace(/_/g, " ")
                  : (NETWORK_TYPE_LABEL[issue.type] || issue.type?.replace(/_/g, " ").toUpperCase());
                const fix       = isGemini ? fixes.find((f: any) => f.bugId === issue.bugId) : null;

                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className={`rounded-xl overflow-hidden border hover:border-white/20 transition-all ${isGemini ? "border-[#f28b82]/20" : "border-white/8"}`}
                    style={{ background: isGemini ? "rgba(242,139,130,0.05)" : "#1e1f20" }}
                  >
                    <div className="p-5 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <SevBadge severity={issue.severity} />
                        <Badge variant="secondary" className="font-mono text-xs flex items-center gap-1 bg-white/8 text-white/65 border-white/10">
                          <TypeIcon className="w-3 h-3" />{typeLabel}
                        </Badge>
                        {isGemini && (
                          <Badge variant="outline" className="text-xs border-[#8ab4f8]/25" style={{ color: "#8ab4f8", background: "rgba(138,180,248,0.08)" }}>
                            Gemini detected
                          </Badge>
                        )}
                        {issue.statusCode && (
                          <Badge variant="outline" className="text-xs border-[#f28b82]/25" style={{ color: "#f28b82", background: "rgba(242,139,130,0.08)" }}>
                            HTTP {issue.statusCode}
                          </Badge>
                        )}
                        {issue.responseTimeMs && (
                          <Badge variant="outline" className="text-xs border-[#fdd663]/25" style={{ color: "#fdd663", background: "rgba(253,214,99,0.08)" }}>
                            {issue.responseTimeMs}ms
                          </Badge>
                        )}
                        {issue.label && <span className="text-xs text-white/35">{issue.label}</span>}
                      </div>
                      <p className="text-sm text-white/80 leading-relaxed">{issue.description}</p>
                      {(issue.elementDescription || issue.element) && (
                        <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8" style={{ background: "rgba(255,255,255,0.03)" }}>
                          {issue.elementDescription || issue.element}
                        </p>
                      )}
                      {issue.url && !isGemini && (
                        <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8 truncate" style={{ background: "rgba(255,255,255,0.03)" }}>
                          {issue.url}
                        </p>
                      )}
                      {(issue.fix || issue.cssFix || fix?.cssFix) && (
                        <div className="rounded-lg p-3 border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.07)" }}>
                          <span className="text-xs font-medium" style={{ color: "#8ab4f8" }}>Suggested Fix: </span>
                          <span className="text-xs text-white/50">{issue.fix || issue.cssFix || fix?.cssFix}</span>
                        </div>
                      )}
                      {(fix?.devtoolsCommand || issue.devtoolsCommand) && (
                        <div className="rounded-lg p-3 border border-[#34A853]/20" style={{ background: "rgba(52,168,83,0.07)" }}>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium flex items-center gap-1" style={{ color: "#81c995" }}>
                              <Terminal className="w-3 h-3" /> DevTools
                            </span>
                            <CopyBtn text={fix?.devtoolsCommand || issue.devtoolsCommand || ""} />
                          </div>
                          <code className="text-xs font-mono break-all" style={{ color: "#81c995" }}>
                            {fix?.devtoolsCommand || issue.devtoolsCommand}
                          </code>
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        )}

        {/* ── ACCESSIBILITY ── */}
        {tab === "a11y" && (
          <div className="space-y-3">
            {domA11yBugs.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <Accessibility className="w-12 h-12 mx-auto mb-3 opacity-20" />
                No accessibility violations found by axe-core. Great job!
              </div>
            ) : (
              domA11yBugs.map((bug: any, idx: number) => {
                const impactColor: Record<string, string> = {
                  critical: "bg-[#f28b82]/12 text-[#f28b82] border-[#f28b82]/25",
                  serious:  "bg-[#fdd663]/10 text-[#fdd663] border-[#fdd663]/25",
                  moderate: "bg-[#fdd663]/8 text-[#fdd663]/70 border-[#fdd663]/20",
                  minor:    "bg-[#81c995]/10 text-[#81c995] border-[#81c995]/25",
                };
                return (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.02 }}
                    className="rounded-xl overflow-hidden border border-white/8 hover:border-white/15 transition-all"
                    style={{ background: "#1e1f20" }}
                  >
                    <div className="p-5 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className={`${impactColor[bug.impact] ?? impactColor.moderate} capitalize font-semibold text-xs`}>
                          {bug.impact}
                        </Badge>
                        <Badge variant="secondary" className="font-mono text-xs bg-white/8 text-white/65 border-white/10">
                          {bug.id}
                        </Badge>
                        <Badge variant="outline" className="text-xs border-[#8ab4f8]/25" style={{ color: "#8ab4f8", background: "rgba(138,180,248,0.06)" }}>
                          <Accessibility className="w-3 h-3 mr-1" /> axe-core
                        </Badge>
                      </div>
                      <p className="text-sm text-white/80 leading-relaxed">{bug.help}</p>
                      <p className="text-xs text-white/40 leading-relaxed">{bug.description}</p>
                      {bug.html && (
                        <code className="block text-xs font-mono text-white/35 px-3 py-2 rounded-lg border border-white/8 break-all" style={{ background: "rgba(255,255,255,0.03)" }}>
                          {bug.html}
                        </code>
                      )}
                      <a
                        href={bug.helpUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs hover:underline"
                        style={{ color: "#8ab4f8" }}
                      >
                        <ExternalLink className="w-3 h-3" /> Learn more on Deque
                      </a>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        )}

        {/* ── SECURITY ── */}
        {tab === "security" && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-4 rounded-xl border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.05)" }}>
              <KeyRound className="w-5 h-5 shrink-0" style={{ color: "#8ab4f8" }} />
              <span className="text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>
                Basic security fuzzing — surface-level XSS/SQLi payload injection on discovered input fields. Review your server response handling for each finding.
              </span>
            </div>
            {securityBugs.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <KeyRound className="w-12 h-12 mx-auto mb-3 opacity-20" />
                No input fields detected or no obvious security concerns found.
              </div>
            ) : (
              securityBugs.map((bug: any, idx: number) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.02 }}
                  className="rounded-xl overflow-hidden border border-white/8 hover:border-white/15 transition-all"
                  style={{ background: "#1e1f20" }}
                >
                  <div className="p-5 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SevBadge severity={bug.severity === "info" ? "minor" : bug.severity} />
                      <Badge variant="secondary" className="font-mono text-xs bg-white/8 text-white/65 border-white/10">
                        {bug.type?.replace(/_/g, " ")}
                      </Badge>
                      <Badge variant="outline" className="text-xs border-[#fdd663]/25" style={{ color: "#fdd663", background: "rgba(253,214,99,0.06)" }}>
                        <Bug className="w-3 h-3 mr-1" /> Security Scan
                      </Badge>
                    </div>
                    <p className="text-sm text-white/80 leading-relaxed">{bug.description}</p>
                    {bug.url && (
                      <p className="text-xs text-white/40 font-mono px-3 py-2 rounded-lg border border-white/8 truncate" style={{ background: "rgba(255,255,255,0.03)" }}>
                        {bug.url}
                      </p>
                    )}
                    <div className="rounded-lg p-3 border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.07)" }}>
                      <span className="text-xs font-medium" style={{ color: "#8ab4f8" }}>Suggested Action: </span>
                      <span className="text-xs text-white/50">
                        {bug.type === "input_discovered"
                          ? "Ensure all inputs are validated server-side. Use parameterized queries and sanitize all user input before rendering."
                          : "Investigate this endpoint. Review server logs and ensure error handling does not leak stack traces."}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        )}

        {/* ── DESIGN INTELLIGENCE ── */}
        {tab === "design" && (
          <div className="space-y-6">
            {/* Cross-page design-token drift — grounded in real computed styles */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-4 rounded-xl border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.05)" }}>
                <Layers className="w-5 h-5 shrink-0" style={{ color: "#8ab4f8" }} />
                <span className="text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>
                  Design-system consistency across every crawled page, computed from real CSS — not a screenshot guess.
                </span>
              </div>
              {designInconsistencies.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground">
                  <Layers className="w-10 h-10 mx-auto mb-2 opacity-20" />
                  No design-token drift detected across pages.
                </div>
              ) : (
                designInconsistencies.map((inc: any, idx: number) => (
                  <div key={idx} className="rounded-xl p-5 space-y-3 border border-white/8" style={{ background: "#1e1f20" }}>
                    <div className="flex flex-wrap items-center gap-2">
                      <SevBadge severity={inc.severity} />
                      <Badge variant="secondary" className="font-mono text-xs bg-white/8 text-white/65 border-white/10">
                        {inc.tokenType}
                      </Badge>
                      <span className="text-sm font-medium text-white/80">{inc.component}</span>
                    </div>
                    <p className="text-sm text-white/50 leading-relaxed">{inc.description}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      {(inc.valuesFound || []).map((v: any, vIdx: number) => (
                        <div key={vIdx} className="p-3 rounded-lg border border-white/8" style={{ background: "rgba(255,255,255,0.03)" }}>
                          <p className="font-mono font-medium mb-1 text-white/70">{v.value}</p>
                          <p className="text-white/40">{(v.sources || []).join(", ")}</p>
                        </div>
                      ))}
                    </div>
                    {inc.recommendation && (
                      <div className="rounded-lg p-3 border border-[#34A853]/20" style={{ background: "rgba(52,168,83,0.07)" }}>
                        <span className="text-xs font-medium" style={{ color: "#81c995" }}>Recommendation: </span>
                        <span className="text-xs text-white/60">{inc.recommendation}</span>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Figma mockup vs. live vision diff */}
            <div className="space-y-3">
              {figmaDeviations.length === 0 ? (
                <div className="text-center py-20 text-muted-foreground">
                  <Figma className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  {currentScan.figmaMatchScore === 100
                    ? "No Figma mockup was uploaded, or no deviations were found."
                    : "No design deviations detected."}
                </div>
              ) : (
              figmaDeviations.map((dev: any, idx: number) => (
                <div key={idx} className="rounded-xl p-5 space-y-3 border border-white/8" style={{ background: "#1e1f20" }}>
                  <div className="flex flex-wrap items-center gap-2">
                    <SevBadge severity={dev.severity} />
                    <span className="text-sm font-medium text-white/80">{dev.element}</span>
                  </div>
                  <p className="text-sm text-white/50 leading-relaxed">{dev.description}</p>
                  {dev.figmaValue && (
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="p-3 rounded-lg border border-[#8ab4f8]/20" style={{ background: "rgba(138,180,248,0.07)" }}>
                        <p className="font-medium mb-1" style={{ color: "#8ab4f8" }}>Figma Design</p>
                        <p className="text-white/45">{dev.figmaValue}</p>
                      </div>
                      <div className="p-3 rounded-lg border border-[#f28b82]/20" style={{ background: "rgba(242,139,130,0.07)" }}>
                        <p className="font-medium mb-1" style={{ color: "#f28b82" }}>Actual App</p>
                        <p className="text-white/45">{dev.actualValue}</p>
                      </div>
                    </div>
                  )}
                  {dev.cssFix && (
                    <div className="rounded-lg p-3 flex items-start justify-between gap-2 border border-[#34A853]/20" style={{ background: "rgba(52,168,83,0.07)" }}>
                      <code className="text-xs font-mono break-all" style={{ color: "#81c995" }}>{dev.cssFix}</code>
                      <CopyBtn text={dev.cssFix} />
                    </div>
                  )}
                </div>
              ))
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
