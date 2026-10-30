"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "../../lib/api-fetch";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clearActiveWorkspace, readActiveWorkspace, saveActiveWorkspace } from "../../lib/workspace-session.mjs";
import {
  STUDIO_STEPPER_SHORT_LABELS,
  getCompletedStudioStages,
  getClearanceReadiness,
  getWorkflowProgress,
  resolveWorkflowNavigation,
} from "../../lib/studio-workflow.mjs";
import { AmbiguityRadarPanel } from "../../components/studio/AmbiguityRadarPanel";
import { Check } from "lucide-react";
import { getRepairDecisionHistory, hasPersistedRepairCompletion } from "../../lib/repair-decisions.mjs";
import { getRepairIneligibilityReason, isRepairPreviewResponse, summarizeRepairEligibility } from "../../lib/repair-preview.mjs";
import { summarizeRepairWorkspace } from "../../lib/repair-workspace.mjs";
import { buildReviewedCopy } from "../../lib/final-audit.mjs";
import { clearWorkflowSession, createFreshStudioContext, createFreshWorkflowSession, readWorkflowSession, resolveWorkflowSession, saveWorkflowSession } from "../../lib/workflow-session.mjs";
import { chooseExampleCopy, NORTHSTAR_EXAMPLE_COPY } from "../../lib/marketing-copy-example.mjs";
import { API_BASE } from "../../lib/api-base";

const MAX_PDF_BYTES = 10 * 1024 * 1024;
type State = { kind: "idle" | "loading" | "success" | "error" | "sample"; message: string };
type PdfOutcome = { filename: string; status: "success" | "error"; extraction?: { document_id?: string | null; candidate_rule_count?: number; size_bytes: number; page_count: number; sha256: string; created_at?: string | null; extraction_status: string }; error_code?: string; message?: string };
type PdfResponse = { results: PdfOutcome[]; summary: { files_succeeded: number; files_rejected: number } };
type GuidelineDocument = { filename: string; size_bytes: number; page_count: number; sha256: string; document_id: string; created_at: string; candidate_rule_count: number; extraction_status: string };
type CandidateRule = { id: string; rule_text: string; category: string | null; source_page: number; source_start_offset: number; source_end_offset: number; source_excerpt: string; review_status: "pending_review" | "approved" | "rejected"; source_filename: string };
type CandidateList = { items: CandidateRule[]; total: number; limit: number; offset: number };
type AuditFinding = { ruleId: string; ruleText: string; sourceFilename: string; sourcePage: number; phrase: string; index: number; decision: "open" | "flagged" | "dismissed" };
type AuditApiFinding = { id: string; rule_id: string | null; fact_id: string | null; term_id: string | null; finding_type: string; status: string; matched_phrase: string; match_start: number; match_end: number; explanation: string; suggested_correction: string | null; source_filename: string | null; source_page: number | null; source_start_offset: number | null; source_end_offset: number | null; evidence_excerpt: string | null; verification_status: "verified" | "uncertain" | "rejected"; verification_reason: string | null; verification_explanation: string | null };
type RepairDecision = { id: string; finding_id: string; action: "accept" | "edit" | "reject"; proposed_replacement: string | null; review_reason: string | null; created_at: string };
type AuditApiResult = { id: string; workspace_id: string; document_id: string | null; content_sha256: string; character_count: number; approved_rules_considered: number; supported_checks_performed: number; rules_unevaluated: number; scope_limitations: string[]; review_status: string; created_at: string; findings: AuditApiFinding[]; decisions: { id: string; finding_id: string; action: string; created_at: string }[]; repair_decisions: RepairDecision[]; clearance: { id: string; decision: string; checks_performed: number; content_sha256: string; created_at: string } | null; submittedText: string };
type RepairApiResult = { audit_id: string; original_sha256: string; findings_reviewed: number; findings_before: number; findings_after: number; status: string; repaired_content: string; replacements: { finding_id: string; start: number; end: number; original: string; replacement: string; reason: string; source_filename: string; source_label: string }[]; limitations: string[] };
type AmbiguityRadarData = { workspace_id: string; minimum_decisions: number; rules: { rule_id: string; rule_text: string; source_filename: string; source_page: number; decision_count: number; dismissals: number; flags: number; accepted_suggestions: number; review_reasons: string[]; dismissal_rate: number; ambiguity_score: number | null; signal: "insufficient_data" | "no_repeated_signal" | "repeated_review_signal" }[]; limitations: string[] };
type ImportedEvidence = { id: string; kind: "fact" | "term"; review_status: "pending_review" | "approved" | "rejected"; source_filename: string; source_row_number: number; source_sha256: string; label: string; detail: string };
type CsvResponse = { summary: { rows_read: number; rows_imported: number; rows_skipped?: number; rows_rejected: number }; errors: { row_number: number; errors: Record<string, string> }[] };
type CsvImportState = { loading: boolean; filename: string; size: number; sourceSha256: string | null; response: CsvResponse | null; error: string };
const emptyCsvState = (): CsvImportState => ({ loading: false, filename: "", size: 0, sourceSha256: null, response: null, error: "" });

function importBatches(items: ImportedEvidence[]) {
  const batches = new Map<string, ImportedEvidence[]>();
  for (const item of items) {
    const key = `${item.kind}:${item.source_sha256}`;
    const group = batches.get(key) ?? [];
    group.push(item);
    batches.set(key, group);
  }
  return Array.from(batches.values()).filter((group: ImportedEvidence[]) => group.some((row) => row.review_status !== "rejected"));
}

function messageFor(response: Response, data: unknown) {
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") return data.detail;
  return `Request failed (${response.status}).`;
}

function protectedMessage(response: Response, data: unknown) {
  if (response.status === 401) return "Authentication is required for this action.";
  if (response.status === 403) return "This action is not permitted for the current session.";
  if (response.status >= 500) return "The Proofmint service could not complete this request. Try again shortly.";
  return messageFor(response, data);
}

export default function StudioPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [workflowReady, setWorkflowReady] = useState(false);
  const [restoreNotice, setRestoreNotice] = useState("");
  const [showExampleReplacePrompt, setShowExampleReplacePrompt] = useState(false);
  const [visitedStages, setVisitedStages] = useState<Set<number>>(() => new Set([1]));
  const [pdf, setPdf] = useState<State>({ kind: "idle", message: "" });
  const [document, setDocument] = useState<GuidelineDocument | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [selectedPdf, setSelectedPdf] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [authPromptOpen, setAuthPromptOpen] = useState(false);
  const [rules, setRules] = useState<CandidateRule[] | null>(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [rulesError, setRulesError] = useState("");
  const [reviewingRule, setReviewingRule] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [copied, setCopied] = useState(false);
  const [facts, setFacts] = useState<CsvImportState>(emptyCsvState);
  const [terms, setTerms] = useState<CsvImportState>(emptyCsvState);
  const [importedEvidence, setImportedEvidence] = useState<ImportedEvidence[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
  const [evidenceActionId, setEvidenceActionId] = useState<string | null>(null);
  const [csvRemoveError, setCsvRemoveError] = useState<{ fact: string; term: string }>({ fact: "", term: "" });
  const [copy, setCopy] = useState("");
  const [auditResult, setAuditResult] = useState<AuditApiResult | null>(null);
  const [auditRestored, setAuditRestored] = useState(false);
  const [auditError, setAuditError] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditRefreshing, setAuditRefreshing] = useState(false);
  const [auditRefreshMessage, setAuditRefreshMessage] = useState("");
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [clearanceLoading, setClearanceLoading] = useState(false);
  const [repairResult, setRepairResult] = useState<RepairApiResult | null>(null);
  const [repairLoading, setRepairLoading] = useState(false);
  const [repairError, setRepairError] = useState("");
  const [repairReload, setRepairReload] = useState(0);
  const [repairDecisionError, setRepairDecisionError] = useState("");
  const [repairDecisionNotice, setRepairDecisionNotice] = useState("");
  const [repairEdits, setRepairEdits] = useState<Record<string, string>>({});
  const [ambiguityRadar, setAmbiguityRadar] = useState<AmbiguityRadarData | null>(null);
  const [ambiguityLoading, setAmbiguityLoading] = useState(false);
  const [ambiguityError, setAmbiguityError] = useState("");
  const [evaluationResult, setEvaluationResult] = useState<Record<string, unknown> | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState("");
  const auditRefreshInFlight = useRef(false);
  const repairDecisionInFlight = useRef(false);
  const sessionGenerationRef = useRef(0);

  useEffect(() => { setVisitedStages((current) => new Set(current).add(step)); }, [step]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => {
    const savedId = readActiveWorkspace(window.sessionStorage);
    const savedFlow = readWorkflowSession(window.sessionStorage);
    if (!savedId) {
      const restored = resolveWorkflowSession(savedFlow, { workspaceId: null, auditId: null, auditHash: null, hasDocument: false, copyMatchesAudit: false });
      setStep(restored.step);
      setVisitedStages(restored.restored && savedFlow ? new Set(savedFlow.visitedStages) : new Set([1]));
      if (restored.reason) setRestoreNotice(`${restored.reason} Returned to Step ${restored.step}.`);
      setWorkflowReady(true);
      return;
    }
    const restorationGeneration = ++sessionGenerationRef.current;
    let cancelled = false;
    const isCurrentRestoration = () => !cancelled
      && sessionGenerationRef.current === restorationGeneration
      && readActiveWorkspace(window.sessionStorage) === savedId;
    setWorkspaceId(savedId); setWorkspaceLoading(true);
    void (async () => {
      let auditId: string | null = null;
      let auditHash: string | null = null;
      let hasDocument = false;
      let copyMatchesAudit = false;
      let workspaceLoaded = false;
      try {
        const response = await apiFetch(`${API_BASE}/api/v1/workspaces/${encodeURIComponent(savedId)}`);
        const data: unknown = await response.json();
        if (!response.ok) throw new Error(messageFor(response, data));
        if (!data || typeof data !== "object" || !("documents" in data) || !Array.isArray(data.documents) || !("latest_audit_id" in data)) throw new Error("The active workspace returned an invalid restoration response.");
        if (!isCurrentRestoration()) return;
        workspaceLoaded = true;
        const workspace = data as { documents: { id: string; source_filename: string; file_size_bytes: number; page_count: number; source_sha256: string; created_at: string }[]; latest_audit_id: string | null };
        const latest = workspace.documents?.[0];
        if (latest) {
          hasDocument = true;
          const restored = { filename: latest.source_filename, size_bytes: latest.file_size_bytes, page_count: latest.page_count, sha256: latest.source_sha256, document_id: latest.id, created_at: latest.created_at, candidate_rule_count: 0, extraction_status: "text_extracted" };
          if (!isCurrentRestoration()) return;
          setDocument(restored); void loadRules(latest.id, savedId);
        }
        if (workspace.latest_audit_id) {
          auditId = workspace.latest_audit_id;
          const auditResponse = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(auditId)}?workspace_id=${encodeURIComponent(savedId)}`);
          const auditData: unknown = await auditResponse.json();
          if (auditResponse.ok && auditData && typeof auditData === "object" && "workspace_id" in auditData && auditData.workspace_id === savedId && "id" in auditData && auditData.id === auditId && "content_sha256" in auditData && typeof auditData.content_sha256 === "string") {
            auditHash = auditData.content_sha256;
            const savedCopy = savedFlow?.workspaceId === savedId && savedFlow.auditId === auditId && savedFlow.auditHash === auditHash ? savedFlow.copy : "";
            if (savedCopy && window.crypto?.subtle) {
              const digest = await window.crypto.subtle.digest("SHA-256", new TextEncoder().encode(savedCopy));
              const computedHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
              copyMatchesAudit = computedHash.toLowerCase() === auditHash.toLowerCase();
            }
            if (!isCurrentRestoration()) return;
            setCopy(savedCopy);
            setAuditResult({ ...(auditData as Omit<AuditApiResult, "submittedText">), submittedText: copyMatchesAudit ? savedCopy : "" });
            setAuditRestored(true);
          }
        } else if (savedFlow?.workspaceId === savedId && savedFlow.auditId === null && savedFlow.auditHash === null) {
          setCopy(savedFlow.copy);
        }
      } catch (error) {
        if (isCurrentRestoration()) setEvidenceError(error instanceof Error ? error.message : "Active workspace could not be restored.");
      }
      finally {
        if (!isCurrentRestoration()) return;
        if (!workspaceLoaded) {
          setStep(1);
          setVisitedStages(new Set([1]));
          setRestoreNotice("The active workspace could not be validated. Returned to Step 1.");
        } else {
          const restored = resolveWorkflowSession(savedFlow, { workspaceId: savedId, auditId, auditHash, hasDocument, copyMatchesAudit });
          setStep(restored.step);
          setVisitedStages(restored.restored && savedFlow ? new Set(savedFlow.visitedStages) : new Set([1]));
          if (restored.reason) setRestoreNotice(`${restored.reason} Returned to Step ${restored.step}.`);
        }
        setWorkspaceLoading(false);
        setWorkflowReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!workflowReady) return;
    saveWorkflowSession(window.sessionStorage, {
      workspaceId,
      auditId: auditResult?.id ?? null,
      auditHash: auditResult?.content_sha256 ?? null,
      step,
      copy,
      visitedStages: Array.from(new Set([...Array.from(visitedStages), step])),
    });
  }, [workflowReady, workspaceId, auditResult, step, copy, visitedStages]);
  const loadRules = async (documentId: string, activeWorkspaceId: string) => {
    const generation = sessionGenerationRef.current;
    setRulesLoading(true); setRulesError(""); setRules(null);
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/guidelines/${encodeURIComponent(documentId)}/rules?workspace_id=${encodeURIComponent(activeWorkspaceId)}&limit=100&offset=0`);
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      if (generation === sessionGenerationRef.current) setRules((data as CandidateList).items || []);
    } catch (error) { if (generation === sessionGenerationRef.current) setRulesError(error instanceof Error ? error.message : "Candidate rules could not be loaded."); }
    finally { if (generation === sessionGenerationRef.current) setRulesLoading(false); }
  };
  const refreshImportedEvidence = useCallback(async () => {
    if (!workspaceId) { setEvidenceError("Upload a guideline PDF to start a workspace before loading evidence."); return; }
    const generation = sessionGenerationRef.current;
    setEvidenceLoading(true); setEvidenceError("");
    try {
      const [factsResponse, termsResponse] = await Promise.all([
        apiFetch(`${API_BASE}/api/v1/facts?workspace_id=${encodeURIComponent(workspaceId)}&limit=100&offset=0`),
        apiFetch(`${API_BASE}/api/v1/terms?workspace_id=${encodeURIComponent(workspaceId)}&limit=100&offset=0`),
      ]);
      const [factsData, termsData] = await Promise.all([factsResponse.json(), termsResponse.json()]);
      if (!factsResponse.ok) throw new Error(messageFor(factsResponse, factsData));
      if (!termsResponse.ok) throw new Error(messageFor(termsResponse, termsData));
      const factItems = (factsData.items || []).map((item: { id: string; review_status: ImportedEvidence["review_status"]; source_filename: string; source_row_number: number; source_sha256: string; approved_statement: string; claim_type: string }) => ({ id: item.id, kind: "fact" as const, review_status: item.review_status, source_filename: item.source_filename, source_row_number: item.source_row_number, source_sha256: item.source_sha256, label: item.approved_statement, detail: `Claim type · ${item.claim_type}` }));
      const termItems = (termsData.items || []).map((item: { id: string; review_status: ImportedEvidence["review_status"]; source_filename: string; source_row_number: number; source_sha256: string; term: string; preferred_form: string | null; category: string | null }) => ({ id: item.id, kind: "term" as const, review_status: item.review_status, source_filename: item.source_filename, source_row_number: item.source_row_number, source_sha256: item.source_sha256, label: item.term, detail: [item.preferred_form && `Preferred form · ${item.preferred_form}`, item.category && `Category · ${item.category}`].filter(Boolean).join(" · ") }));
      if (generation === sessionGenerationRef.current) setImportedEvidence([...factItems, ...termItems]);
    } catch (error) { if (generation === sessionGenerationRef.current) setEvidenceError(error instanceof Error ? error.message : "Imported evidence could not be loaded."); }
    finally { if (generation === sessionGenerationRef.current) setEvidenceLoading(false); }
  }, [workspaceId]);
  useEffect(() => { if (workflowReady && workspaceId) void refreshImportedEvidence(); }, [workflowReady, workspaceId, refreshImportedEvidence]);
  const decideImportedEvidence = async (item: ImportedEvidence, action: "approve" | "reject") => {
    const generation = sessionGenerationRef.current;
    setEvidenceActionId(item.id); setEvidenceError("");
    try {
      const collection = item.kind === "fact" ? "facts" : "terms";
      const response = await apiFetch(`${API_BASE}/api/v1/${collection}/${encodeURIComponent(item.id)}/${action}?workspace_id=${encodeURIComponent(workspaceId || "")}`, { method: "POST" });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      const updated = data as { review_status: ImportedEvidence["review_status"] };
      if (generation === sessionGenerationRef.current) setImportedEvidence((current) => current.map((record) => record.id === item.id ? { ...record, review_status: updated.review_status } : record));
    } catch (error) { if (generation === sessionGenerationRef.current) setEvidenceError(error instanceof Error ? error.message : "Evidence review action failed."); }
    finally { if (generation === sessionGenerationRef.current) setEvidenceActionId(null); }
  };
  const reviewRule = async (ruleId: string, action: "approve" | "reject") => {
    const generation = sessionGenerationRef.current;
    setReviewingRule(ruleId); setReviewError("");
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/rules/${encodeURIComponent(ruleId)}/${action}?workspace_id=${encodeURIComponent(workspaceId || "")}`, { method: "POST" });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      const updated = data as CandidateRule;
      if (generation === sessionGenerationRef.current) setRules((current) => current?.map((rule) => rule.id === updated.id ? updated : rule) ?? current);
    } catch (error) { if (generation === sessionGenerationRef.current) setReviewError(error instanceof Error ? error.message : "Review decision could not be saved."); }
    finally { if (generation === sessionGenerationRef.current) setReviewingRule(null); }
  };
  const restart = () => {
    sessionGenerationRef.current += 1;
    auditRefreshInFlight.current = false;
    repairDecisionInFlight.current = false;
    clearActiveWorkspace(window.sessionStorage);
    clearWorkflowSession(window.sessionStorage);
    const freshContext = createFreshStudioContext();
    const freshSession = createFreshWorkflowSession();
    saveWorkflowSession(window.sessionStorage, freshSession);
    setWorkspaceId(freshSession.workspaceId); setWorkspaceLoading(false);
    setStep(freshContext.step); setVisitedStages(new Set(freshContext.visitedStages)); setRestoreNotice(""); setShowExampleReplacePrompt(false);
    setPdf({ kind: "idle", message: "" }); setDocument(freshContext.document); setRules(freshContext.rules); setRulesLoading(false); setRulesError(""); setReviewError(""); setReviewingRule(null); setCopied(false);
    setSelectedPdf(null); setPreviewOpen(false); if (previewUrl) URL.revokeObjectURL(previewUrl); setPreviewUrl(null);
    setFacts(emptyCsvState()); setTerms(emptyCsvState()); setImportedEvidence(freshContext.importedEvidence); setEvidenceLoading(false); setEvidenceError(""); setEvidenceActionId(null); setCsvRemoveError({ fact: "", term: "" });
    setCopy(freshContext.copy); setAuditResult(freshContext.auditResult); setAuditRestored(freshContext.auditRestored); setAuditError(""); setAuditLoading(false); setAuditRefreshing(false); setAuditRefreshMessage(""); setDecisionLoading(false); setClearanceLoading(false);
    setRepairResult(freshContext.repairResult); setRepairLoading(false); setRepairError(""); setRepairDecisionError(""); setRepairDecisionNotice(""); setRepairEdits({});
    setAmbiguityRadar(null); setAmbiguityLoading(false); setAmbiguityError(""); setEvaluationResult(null); setEvaluationLoading(false); setEvaluationError("");
  };
  const goToStep = (target: number) => {
    if (target === 7 && !hasPersistedRepairCompletion(auditResult, repairResult, { loading: repairLoading, error: repairError })) return;
    const hasPersistedAudit = Boolean(auditResult);
    const auditedCopyIsCurrent = Boolean(auditResult && (auditResult.submittedText === copy || (auditRestored && auditResult.submittedText === "")));
    setStep(resolveWorkflowNavigation(target, hasPersistedAudit, auditedCopyIsCurrent).stage);
  };
  const repairHistory = getRepairDecisionHistory(auditResult) as RepairDecision[];
  const repairStageComplete = hasPersistedRepairCompletion(auditResult, repairResult, { loading: repairLoading, error: repairError });
  const completedStages = useMemo(() => getCompletedStudioStages({
    hasGuidelineDocument: Boolean(document),
    hasActiveCsvImport: importedEvidence.some((item) => item.review_status !== "rejected"),
    hasRuleReviewDecision: Boolean(rules?.some((rule) => rule.review_status !== "pending_review")),
    hasPersistedAudit: Boolean(auditResult),
    hasPersistedRepairDecision: repairStageComplete,
  }), [document, importedEvidence, rules, auditResult, repairStageComplete]);
  const workflowProgress = getWorkflowProgress(step, completedStages, visitedStages);
  const renderStepper = () => <ol className="mb-10 flex min-w-0 gap-2 overflow-x-auto pb-2" aria-label="Launch Studio progress">{workflowProgress.map((stage) => <li key={stage.id} className="flex min-w-[112px] items-center gap-2"><button type="button" aria-current={stage.state === "active" ? "step" : undefined} aria-label={`${stage.number}. ${STUDIO_STEPPER_SHORT_LABELS[stage.number as keyof typeof STUDIO_STEPPER_SHORT_LABELS]}: ${stage.state}`} onClick={() => goToStep(stage.number)} className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${stage.state === "active" ? "border-verification-mint bg-verification-mint text-graphite-base" : stage.state === "complete" ? "border-verification-mint text-verification-mint" : stage.state === "visited" ? "border-warning-copper/60 text-warning-copper" : "border-border-structural text-secondary"}`}>{stage.state === "complete" ? <Check aria-hidden="true" size={16} strokeWidth={2.5} /> : stage.number}</button><span className="text-xs text-secondary">{STUDIO_STEPPER_SHORT_LABELS[stage.number as keyof typeof STUDIO_STEPPER_SHORT_LABELS]}</span></li>)}</ol>;
  const uploadPdf = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (file.size > MAX_PDF_BYTES) { setPdf({ kind: "error", message: "This file exceeds the 10 MiB PDF limit." }); event.target.value = ""; return; }
    const replacingIngestedPdf = Boolean(document && workspaceId);
    if (replacingIngestedPdf) restart();
    const generation = sessionGenerationRef.current;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file)); setSelectedPdf(file); setPreviewOpen(false);
    setPdf({ kind: "idle", message: "" });
    try {
      const session = await apiFetch(`${API_BASE}/api/v1/auth/me`);
      if (session.status === 401) {
        setAuthPromptOpen(true);
        setPdf({ kind: "idle", message: "Sign in to continue. The PDF has not been uploaded." });
        event.target.value = "";
        return;
      }
      if (!session.ok) {
        const sessionData: unknown = await session.json().catch(() => null);
        setPdf({ kind: "error", message: protectedMessage(session, sessionData) });
        event.target.value = "";
        return;
      }
    } catch {
      setPdf({ kind: "error", message: "The API could not be reached while checking your session. No file was uploaded." });
      event.target.value = "";
      return;
    }
    setPdf({ kind: "loading", message: `Uploading ${file.name}…` });
    const form = new FormData(); form.append("files", file);
    if (!replacingIngestedPdf && workspaceId) form.append("workspace_id", workspaceId);
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/guidelines/ingest`, { method: "POST", body: form });
      const data: unknown = await response.json().catch(() => null);
      if (generation !== sessionGenerationRef.current) return;
      if (!response.ok) {
        if (response.status === 401) { setAuthPromptOpen(true); setPdf({ kind: "idle", message: "Your session is required before upload. The PDF was not uploaded." }); return; }
        setPdf({ kind: "error", message: protectedMessage(response, data) }); return;
      }
      const result = data as PdfResponse & { workspace_id?: string | null }; const outcome = result.results?.[0];
      if (!outcome || outcome.status === "error") { setPdf({ kind: "error", message: outcome?.message || "The PDF was not accepted." }); return; }
      const extraction = outcome.extraction;
      if (!extraction?.document_id) { setPdf({ kind: "error", message: "The API accepted the file but did not return a persistent document ID." }); return; }
      if (!result.workspace_id) { setPdf({ kind: "error", message: "The API accepted the PDF without returning a workspace ID." }); return; }
      setWorkspaceId(result.workspace_id); saveActiveWorkspace(window.sessionStorage, result.workspace_id);
      const saved = { filename: outcome.filename, size_bytes: extraction.size_bytes, page_count: extraction.page_count, sha256: extraction.sha256, document_id: extraction.document_id, created_at: extraction.created_at || "", candidate_rule_count: extraction.candidate_rule_count ?? 0, extraction_status: extraction.extraction_status };
      setDocument(saved);
      setPdf({ kind: "success", message: "Guideline ingested and document metadata persisted in a new workspace. Original PDF bytes are retained in private server-side storage." }); void loadRules(saved.document_id, result.workspace_id);
      } catch { if (generation === sessionGenerationRef.current) setPdf({ kind: "error", message: "The API could not be reached. No upload was persisted." }); }
    finally { event.target.value = ""; }
  };
  const clearPdfSelection = () => {
    if (document && workspaceId) {
      restart();
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null); setSelectedPdf(null); setPreviewOpen(false); setPdf({ kind: "idle", message: "" });
  };
  const removeImportBatch = async (kind: "fact" | "term", batchId: string) => {
    if (!workspaceId || evidenceActionId) return;
    const generation = sessionGenerationRef.current;
    setEvidenceActionId(batchId); setCsvRemoveError((current) => ({ ...current, [kind]: "" }));
    try {
      const endpoint = kind === "fact" ? "facts" : "terms";
      const response = await apiFetch(`${API_BASE}/api/v1/imports/${endpoint}/${encodeURIComponent(batchId)}/remove?workspace_id=${encodeURIComponent(workspaceId)}`, { method: "POST" });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 401) { router.push(`/auth?returnTo=${encodeURIComponent("/studio")}`); return; }
        throw new Error(messageFor(response, data));
      }
      if (generation !== sessionGenerationRef.current) return;
      await refreshImportedEvidence();
      if (kind === "fact") setFacts(emptyCsvState()); else setTerms(emptyCsvState());
    } catch (error) { if (generation === sessionGenerationRef.current) setCsvRemoveError((current) => ({ ...current, [kind]: error instanceof Error ? error.message : "Import batch removal failed. Retry the removal." })); }
    finally { if (generation === sessionGenerationRef.current) setEvidenceActionId(null); }
  };
  const clearCsvSelection = (kind: "fact" | "term") => {
    const state = kind === "fact" ? facts : terms;
    const importedBatch = state.response && state.sourceSha256
      ? importedEvidence.find((item) => item.kind === kind && item.source_sha256 === state.sourceSha256)
      : undefined;
    if (importedBatch) { void removeImportBatch(kind, importedBatch.source_sha256); return; }
    if (kind === "fact") setFacts(emptyCsvState()); else setTerms(emptyCsvState());
  };

  const uploadCsv = async (endpoint: "facts" | "terms", event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    const generation = sessionGenerationRef.current;
    const setState = endpoint === "facts" ? setFacts : setTerms;
    if (!workspaceId) { setState({ loading: false, filename: file.name, size: file.size, sourceSha256: null, response: null, error: "Upload a guideline PDF to start a workspace before importing evidence." }); event.target.value = ""; return; }
    if (file.size === 0) { setState({ loading: false, filename: file.name, size: 0, sourceSha256: null, response: null, error: "The selected CSV is empty." }); event.target.value = ""; return; }
    const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
    if (generation !== sessionGenerationRef.current) { event.target.value = ""; return; }
    const sourceSha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    setState({ loading: true, filename: file.name, size: file.size, sourceSha256, response: null, error: "" });
    const form = new FormData(); form.append("file", file); form.append("workspace_id", workspaceId);
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/${endpoint}/import`, { method: "POST", body: form });
      const data: unknown = await response.json().catch(() => null);
      if (generation !== sessionGenerationRef.current) return;
      if (!response.ok) { setState({ loading: false, filename: file.name, size: file.size, sourceSha256, response: null, error: messageFor(response, data) }); return; }
      const result = data as CsvResponse;
      setState({ loading: false, filename: file.name, size: file.size, sourceSha256, response: result, error: "" });
      void refreshImportedEvidence();
    } catch { if (generation === sessionGenerationRef.current) setState({ loading: false, filename: file.name, size: file.size, sourceSha256, response: null, error: "Could not reach the API. Check NEXT_PUBLIC_API_URL and that the backend is running." }); }
    finally { event.target.value = ""; }
  };
  const runAudit = async () => {
    if (!copy.trim() || auditLoading) return;
    const generation = sessionGenerationRef.current;
    setAuditLoading(true); setAuditError("");
    try {
      if (!workspaceId) throw new Error("Upload a guideline PDF to start a workspace before running an audit.");

      const response = await apiFetch(`${API_BASE}/api/v1/audits`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: copy, document_id: document?.document_id || null, workspace_id: workspaceId }) });
      const data: unknown = await response.json().catch(() => null);
      if (generation !== sessionGenerationRef.current) return;
      if (!response.ok) throw new Error(messageFor(response, data));
      setAuditRestored(false);
      setAuditResult({ ...(data as Omit<AuditApiResult, "submittedText">), submittedText: copy }); setStep(5);
    } catch (error) { if (generation === sessionGenerationRef.current) setAuditError(error instanceof Error ? error.message : "Audit request failed."); }
    finally { if (generation === sessionGenerationRef.current) setAuditLoading(false); }
  };
  const refreshAudit = async (auditId: string) => {
    if (auditRefreshInFlight.current) return;
    const generation = sessionGenerationRef.current;
    auditRefreshInFlight.current = true; setAuditRefreshing(true); setAuditError(""); setAuditRefreshMessage("");
    try {
      if (!workspaceId) throw new Error("The active workspace is missing. Upload a PDF to start a session.");
      const response = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(auditId)}?workspace_id=${encodeURIComponent(workspaceId)}`);
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      if (generation !== sessionGenerationRef.current) return;
      if (!data || typeof data !== "object" || !("id" in data) || data.id !== auditId || !("workspace_id" in data) || data.workspace_id !== workspaceId) throw new Error("The API returned an audit outside the active workspace.");
      setAuditResult((current) => current ? ({ ...(data as Omit<AuditApiResult, "submittedText">), submittedText: current.submittedText }) : current);
      setAuditRefreshMessage("Persisted audit refreshed from the server.");
    } catch (error) { if (generation === sessionGenerationRef.current) setAuditError(error instanceof Error ? error.message : "Audit could not be refreshed."); }
    finally { if (generation === sessionGenerationRef.current) { auditRefreshInFlight.current = false; setAuditRefreshing(false); } }
  };
  const decideFinding = async (findingId: string, action: "accept_suggestion" | "dismiss" | "flag") => {
    if (!auditResult || decisionLoading) return; setDecisionLoading(true); setAuditError("");
    const generation = sessionGenerationRef.current;
    try { if (!workspaceId) throw new Error("The active workspace is missing."); const response = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(auditResult.id)}/findings/${encodeURIComponent(findingId)}/decisions?workspace_id=${encodeURIComponent(workspaceId)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) }); const data: unknown = await response.json().catch(() => null); if (!response.ok) throw new Error(messageFor(response, data)); if (generation === sessionGenerationRef.current) setAuditResult({ ...(data as Omit<AuditApiResult, "submittedText">), submittedText: auditResult.submittedText }); }
    catch (error) { if (generation === sessionGenerationRef.current) setAuditError(error instanceof Error ? error.message : "Finding decision failed."); }
    finally { if (generation === sessionGenerationRef.current) setDecisionLoading(false); }
  };
  const decideRepair = async (findingId: string, action: "accept" | "edit" | "reject", replacement: string | null) => {
    if (!auditResult || !workspaceId || repairDecisionInFlight.current || !repairResult?.replacements.some((item) => item.finding_id === findingId)) return;
    const generation = sessionGenerationRef.current;
    repairDecisionInFlight.current = true;
    setDecisionLoading(true); setRepairDecisionError(""); setRepairDecisionNotice("");
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(auditResult.id)}/findings/${encodeURIComponent(findingId)}/repair-decisions?workspace_id=${encodeURIComponent(workspaceId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, content: auditResult.submittedText, replacement }),
      });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      if (generation !== sessionGenerationRef.current) return;
      if (!data || typeof data !== "object" || !("id" in data) || data.id !== auditResult.id || !("workspace_id" in data) || data.workspace_id !== workspaceId) throw new Error("The API returned a decision outside the active audit workspace.");
      setAuditResult({ ...(data as Omit<AuditApiResult, "submittedText">), submittedText: auditResult.submittedText });
      setRepairDecisionNotice(action === "accept" ? "Acceptance saved to this audit. The submitted copy remains unchanged." : action === "edit" ? "Edited proposal saved to this audit. The submitted copy remains unchanged." : "Rejection saved to this audit; the proposal will not be offered again.");
      if (action === "reject") setRepairResult((current) => current ? { ...current, replacements: current.replacements.filter((item) => item.finding_id !== findingId), status: current.replacements.length <= 1 ? "no_supported_repairs" : current.status } : current);
    } catch (error) { if (generation === sessionGenerationRef.current) setRepairDecisionError(error instanceof Error ? error.message : "Repair decision could not be persisted."); }
    finally { if (generation === sessionGenerationRef.current) { repairDecisionInFlight.current = false; setDecisionLoading(false); } }
  };
  const decideClearance = async (decision: "cleared" | "hold") => {
    if (!auditResult || clearanceLoading) return; const generation = sessionGenerationRef.current; setClearanceLoading(true); setAuditError("");
    try { if (!workspaceId) throw new Error("The active workspace is missing."); const response = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(auditResult.id)}/clearance?workspace_id=${encodeURIComponent(workspaceId)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) }); const data: unknown = await response.json().catch(() => null); if (!response.ok) throw new Error(messageFor(response, data)); if (generation === sessionGenerationRef.current) setAuditResult({ ...(data as Omit<AuditApiResult, "submittedText">), submittedText: auditResult.submittedText }); }
    catch (error) { if (generation === sessionGenerationRef.current) setAuditError(error instanceof Error ? error.message : "Clearance decision failed."); }
    finally { if (generation === sessionGenerationRef.current) setClearanceLoading(false); }
  };
  const loadAmbiguityRadar = useCallback(async () => {
    if (!workspaceId || ambiguityLoading) return;
    const generation = sessionGenerationRef.current;
    setAmbiguityLoading(true); setAmbiguityError("");
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/ambiguity-radar?workspace_id=${encodeURIComponent(workspaceId)}`);
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      if (generation !== sessionGenerationRef.current) return;
      if (!data || typeof data !== "object" || !("workspace_id" in data) || data.workspace_id !== workspaceId) throw new Error("The API returned analysis outside the active workspace.");
      setAmbiguityRadar(data as AmbiguityRadarData);
    } catch (error) { if (generation === sessionGenerationRef.current) setAmbiguityError(error instanceof Error ? error.message : "Ambiguity analysis could not be loaded."); }
    finally { if (generation === sessionGenerationRef.current) setAmbiguityLoading(false); }
  }, [workspaceId, ambiguityLoading]);
  const loadEvaluation = useCallback(async () => {
    if (evaluationLoading) return;
    const generation = sessionGenerationRef.current;
    setEvaluationLoading(true); setEvaluationError("");
    try {
      const response = await apiFetch(`${API_BASE}/api/v1/evaluation`);
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(messageFor(response, data));
      if (generation !== sessionGenerationRef.current) return;
      if (!data || typeof data !== "object" || !("dataset" in data) || !("finding_metrics" in data)) throw new Error("The API returned an invalid evaluation report.");
      setEvaluationResult(data as Record<string, unknown>);
    } catch (error) { if (generation === sessionGenerationRef.current) setEvaluationError(error instanceof Error ? error.message : "Labelled evaluation could not be loaded."); }
    finally { if (generation === sessionGenerationRef.current) setEvaluationLoading(false); }
  }, [evaluationLoading]);
  useEffect(() => {
    if (!workflowReady || step !== 7) return;
    if (!evaluationResult && !evaluationLoading && !evaluationError) void loadEvaluation();
    if (workspaceId && !ambiguityRadar && !ambiguityLoading && !ambiguityError) void loadAmbiguityRadar();
  }, [workflowReady, step, workspaceId, evaluationResult, evaluationLoading, evaluationError, ambiguityRadar, ambiguityLoading, ambiguityError, loadEvaluation, loadAmbiguityRadar]);
  const repairAuditId = auditResult?.id;
  const repairContent = auditResult?.submittedText;
  useEffect(() => {
    if (![6, 7].includes(step) || !repairAuditId || !repairContent || !workspaceId) return;
    let current = true;
    const generation = sessionGenerationRef.current;
    const load = async () => {
      setRepairLoading(true); setRepairError(""); setRepairResult(null);
      try {
        const response = await apiFetch(`${API_BASE}/api/v1/audits/${encodeURIComponent(repairAuditId)}/repair?workspace_id=${encodeURIComponent(workspaceId)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: repairContent }) });
        const data: unknown = await response.json().catch(() => null);
        if (!response.ok) throw new Error(messageFor(response, data));
        if (!isRepairPreviewResponse(data, repairAuditId, auditResult?.content_sha256 ?? "")) throw new Error("The repair preview did not match the active audit and submitted-copy hash.");
        if (current && generation === sessionGenerationRef.current) setRepairResult(data as RepairApiResult);
      } catch (error) { if (current && generation === sessionGenerationRef.current) setRepairError(error instanceof Error ? error.message : "Repair preview could not be loaded."); }
      finally { if (current && generation === sessionGenerationRef.current) setRepairLoading(false); }
    };
    void load();
    return () => { current = false; };
  }, [step, repairAuditId, repairContent, workspaceId, auditResult?.content_sha256, repairReload]);
  const repairEligibility = summarizeRepairEligibility(auditResult?.findings ?? []);
  const latestRepairDecision = (findingId: string) => repairHistory.filter((decision) => decision.finding_id === findingId).at(-1)?.action ?? null;
  const openRepairFindings = auditResult?.findings.filter((finding) => ["pending_review", "flagged"].includes(finding.status)) ?? [];
  const repairSummary = summarizeRepairWorkspace(auditResult, repairResult) as { totalFindings: number; dismissedFindings: number; eligibleFindings: number; awaitingDecision: number; accepted: number; edited: number; rejected: number; withoutEligibleRepair: number; unsupportedFindings: AuditApiFinding[]; closedFindings: AuditApiFinding[]; latestByFinding: Map<string, RepairDecision> };
  const reviewedCopy = auditResult && repairResult ? buildReviewedCopy(auditResult.submittedText, auditResult.findings, repairHistory, repairResult.replacements) : { content: null, applied: 0, unavailable: true };
  const clearanceReadiness = getClearanceReadiness(auditResult?.findings ?? [], Boolean(auditResult && (auditResult.submittedText === copy || (auditRestored && auditResult.submittedText === ""))));
  const evaluationSection = (key: string) => {
    const value = evaluationResult?.[key];
    return value && typeof value === "object" ? value as Record<string, unknown> : {};
  };
  const findingMetrics = evaluationSection("finding_metrics");
  const evidenceMetrics = evaluationSection("evidence_verification");
  const observedEvidence = evidenceMetrics.observed && typeof evidenceMetrics.observed === "object" ? evidenceMetrics.observed as Record<string, unknown> : {};
  const expectedEvidence = evidenceMetrics.expected && typeof evidenceMetrics.expected === "object" ? evidenceMetrics.expected as Record<string, unknown> : {};
  const consistencyMetrics = evaluationSection("run_consistency");
  const repairMetrics = evaluationSection("repair_validity");
  if (!workflowReady) return <main className="min-h-screen px-4 pb-12 pt-24 sm:px-6 lg:px-12"><div className="mx-auto max-w-6xl"><p role="status" className="text-sm text-secondary">Restoring workflow session…</p></div></main>;
  const authPrompt = authPromptOpen ? <div className="fixed inset-0 z-[60] flex items-center justify-center bg-graphite-base/80 p-4" role="dialog" aria-modal="true" aria-labelledby="auth-prompt-title"><div className="w-full max-w-md border border-border-structural bg-charcoal-elevated p-6 shadow-2xl"><h2 id="auth-prompt-title" className="text-xl font-semibold text-off-white">Sign in to continue</h2><p className="mt-3 text-sm leading-relaxed text-secondary">Create an account or sign in to save your brand workspaces, audits and review decisions securely. Your PDF has not been uploaded.</p><div className="mt-6 flex flex-wrap gap-3"><Link href={`/auth?returnTo=${encodeURIComponent("/studio")}`} className="bg-verification-mint px-4 py-3 text-sm font-semibold text-graphite-base" onClick={() => setAuthPromptOpen(false)}>Continue to authentication</Link><button type="button" className="border border-border-structural px-4 py-3 text-sm text-off-white" onClick={() => setAuthPromptOpen(false)}>Cancel</button></div></div></div> : null;
  if (step === 6) return <>{authPrompt}<main className="min-h-screen px-4 pb-12 pt-24 sm:px-6 lg:px-12"><div className="mx-auto max-w-6xl">
    {restoreNotice && <p role="status" className="mb-5 border border-warning-copper/40 p-3 text-sm text-warning-copper">{restoreNotice}</p>}
    <div className="mb-10 flex flex-wrap items-end justify-between gap-4"><div><p className="font-mono text-xs uppercase tracking-[0.2em] text-verification-mint">Interactive walkthrough</p><h1 className="mt-2 text-3xl font-semibold text-off-white sm:text-4xl">Launch Studio</h1><p className="mt-2 text-secondary">Human approval remains separate from imports and sample decisions.</p>{workspaceId && <p className="mt-2 break-all font-mono text-xs text-secondary">Active session · {workspaceId}</p>}</div><button type="button" onClick={restart} className="text-sm text-secondary underline underline-offset-4 hover:text-off-white">Start new session</button></div>
    {renderStepper()}
    <section className="min-h-[420px] border border-border-structural bg-surface-container-low p-6 sm:p-10">
      <h2 className="text-xl font-semibold text-off-white">6. Repair</h2>
      <p className="mt-2 text-secondary">Review evidence-backed corrections and record a decision. The original submitted copy is never changed.</p>
      <dl aria-label="Repair status summary" className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">{[["Findings", repairSummary.totalFindings], ["Eligible", repairSummary.eligibleFindings], ["Awaiting", repairSummary.awaitingDecision], ["Accepted", repairSummary.accepted], ["Edited", repairSummary.edited], ["Rejected", repairSummary.rejected], ["No supported repair", repairSummary.withoutEligibleRepair]].map(([label, count]) => <div key={label} className="border border-border-structural bg-graphite-base p-3"><dt className="text-xs text-secondary">{label}</dt><dd className="mt-1 text-lg font-semibold text-off-white">{count}</dd></div>)}</dl>
      {repairLoading && <p role="status" className="mt-6 text-sm text-secondary">Loading and rechecking repair proposals…</p>}
      {repairError && <p role="alert" className="mt-6 text-sm text-warning-copper">Repair proposals could not be loaded: {repairError}</p>}
      {repairDecisionNotice && <p role="status" className="mt-4 border border-verification-mint/40 p-3 text-sm text-verification-mint">{repairDecisionNotice}</p>}
      {repairDecisionError && <p role="alert" className="mt-4 border border-warning-copper/40 p-3 text-sm text-warning-copper">Decision not saved: {repairDecisionError}</p>}
      {repairResult?.status === "preview_available" && <>
        <section className="mt-6 border border-border-structural bg-graphite-base p-4">
          <h3 className="text-sm font-semibold text-off-white">Original submitted copy · unchanged</h3>
          <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap break-words text-sm text-secondary">{repairContent}</pre>
        </section>
        <div className="mt-4 space-y-4">{repairResult.replacements.map((replacement) => {
          const finding = auditResult?.findings.find((item) => item.id === replacement.finding_id);
          const saved = repairSummary.latestByFinding.get(replacement.finding_id);
          const editable = repairEdits[replacement.finding_id] ?? replacement.replacement;
          return <article key={replacement.finding_id} className="border border-border-structural bg-graphite-base p-5">
            <p className="text-xs uppercase tracking-wider text-verification-mint">Supported repair · {replacement.source_filename}</p>
            <p className="mt-3 text-xs text-secondary">Finding ID · <code>{replacement.finding_id}</code></p>
            <p className="mt-3 text-sm text-secondary">Finding: {finding?.finding_type.replaceAll("_", " ") ?? "preferred terminology"} · matched text <mark className="bg-warning-copper/30 text-off-white">{replacement.original}</mark></p>
            {finding && <p className="mt-2 border-l-2 border-warning-copper/50 pl-3 text-sm text-secondary">Context: {repairContent?.slice(Math.max(0, finding.match_start - 90), Math.min(repairContent.length, finding.match_end + 90))}</p>}
            <p className="mt-3 text-sm text-secondary">Approved source: <span className="text-off-white">{replacement.source_label}</span></p>
            <p className="mt-3 text-sm text-secondary">Proposed correction: <span className="text-verification-mint">{replacement.replacement}</span></p>
            <p className="mt-3 text-sm text-secondary">Why: {replacement.reason}</p>
            <p className="mt-3 text-xs text-secondary">Evidence status: {finding?.verification_status ?? "verified by server recheck"}. The proposal is limited to this approved preferred-term mapping.</p>
            {finding?.evidence_excerpt && <p className="mt-2 text-xs text-secondary">Supporting evidence: {finding.evidence_excerpt}</p>}
            <p className="mt-3 text-xs text-secondary">Preview only. Accepting or editing records a reviewer decision; it does not apply the correction to the submitted copy.</p>
            <p className={`mt-3 text-sm ${saved ? "text-verification-mint" : "text-warning-copper"}`}>Human status: {saved ? (saved.action === "accept" ? "Accepted" : saved.action === "edit" ? "Edited" : "Rejected") : "Pending"}{saved?.proposed_replacement ? ` · ${saved.proposed_replacement}` : ""}{saved ? ` · ${new Date(saved.created_at).toLocaleString()}` : ""}</p>
            <label className="mt-4 block text-xs text-secondary">Edit proposed wording<textarea value={editable} onChange={(event) => setRepairEdits((current) => ({ ...current, [replacement.finding_id]: event.target.value }))} maxLength={500} className="mt-2 min-h-20 w-full border border-border-structural bg-surface-container-low p-3 text-sm text-off-white" /></label>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" aria-label={`Accept proposal for finding ${replacement.finding_id}`} disabled={decisionLoading || auditResult?.submittedText !== copy} onClick={() => void decideRepair(replacement.finding_id, "accept", replacement.replacement)} className="bg-verification-mint px-3 py-2 text-sm font-semibold text-graphite-base disabled:opacity-50">Accept</button>
              <button type="button" aria-label={`Save edited proposal for finding ${replacement.finding_id}`} disabled={decisionLoading || !editable.trim() || auditResult?.submittedText !== copy} onClick={() => void decideRepair(replacement.finding_id, "edit", editable)} className="border border-border-structural px-3 py-2 text-sm text-off-white disabled:opacity-50">Save edit</button>
              <button type="button" aria-label={`Reject proposal for finding ${replacement.finding_id}`} disabled={decisionLoading || auditResult?.submittedText !== copy} onClick={() => void decideRepair(replacement.finding_id, "reject", null)} className="border border-warning-copper/50 px-3 py-2 text-sm text-warning-copper disabled:opacity-50">Reject proposal</button>
            </div>
          </article>;
        })}</div>
      </>}
      {repairResult?.status === "preview_available" && repairSummary.unsupportedFindings.length > 0 && <section className="mt-5 border border-border-structural p-5"><h3 className="font-semibold text-off-white">Findings without an actionable proposal</h3><ul className="mt-3 space-y-3">{repairSummary.unsupportedFindings.map((finding) => <li key={finding.id} className="border-l-2 border-border-structural pl-3 text-sm text-secondary"><code className="text-xs">{finding.id}</code><p className="mt-1 text-off-white">{finding.finding_type.replaceAll("_", " ")} · {finding.matched_phrase}</p><p className="mt-1 text-xs">{getRepairIneligibilityReason(finding, latestRepairDecision(finding.id))}</p></li>)}</ul></section>}
      {repairResult && repairResult.status !== "preview_available" && <section className="mt-6 border border-border-structural p-5">
        <h3 className="font-semibold text-off-white">Repair availability</h3>
        {repairResult.status === "no_findings" && <p className="mt-2 text-sm text-secondary">This audit contains no findings to repair.</p>}
        {repairResult.status === "no_open_findings" && <p className="mt-2 text-sm text-secondary">No findings remain open for repair. Current states: {repairEligibility.dismissed} dismissed, {repairEligibility.resolved} resolved, {repairEligibility.informational} informational. Repair does not reopen closed findings.</p>}
        {repairResult.status === "no_supported_repairs" && <>
          <p className="mt-2 text-sm text-secondary">The server returned no currently supported proposal for {openRepairFindings.length} open finding(s). Only verified preferred-terminology matches with an approved replacement form receive deterministic repairs.</p>
          {openRepairFindings.length > 0 && <ul className="mt-4 space-y-3">{openRepairFindings.map((finding) => <li key={finding.id} className="border-l-2 border-border-structural pl-3 text-sm text-secondary"><span className="text-off-white">{finding.finding_type.replaceAll("_", " ")} · {finding.matched_phrase}</span><span className="block text-xs">{getRepairIneligibilityReason(finding, latestRepairDecision(finding.id))}</span></li>)}</ul>}
        </>}
        {repairSummary.closedFindings.length > 0 && <section className="mt-4 border-t border-border-structural pt-4"><h4 className="text-sm font-semibold text-off-white">Closed findings · unchanged</h4><ul className="mt-3 space-y-3">{repairSummary.closedFindings.map((finding) => <li key={finding.id} className="border-l-2 border-border-structural pl-3 text-sm text-secondary"><span className="text-off-white">{finding.status.replaceAll("_", " ")} · {finding.finding_type.replaceAll("_", " ")} · {finding.matched_phrase}</span><span className="block text-xs">{getRepairIneligibilityReason(finding, latestRepairDecision(finding.id))}</span></li>)}</ul><p className="mt-3 text-xs text-secondary">Repair does not reopen or change dismissed/resolved findings.</p></section>}
      </section>}
      {!repairLoading && !repairError && !repairResult && <p className="mt-6 border border-border-structural p-5 text-secondary">{!auditResult ? "Run an audit first to request a repair preview." : !repairContent ? "The server retains only the original text hash. Persisted decisions are shown below; restore the exact audited copy and run a new audit to request another preview." : "No repair preview has been loaded."}</p>}
      {auditError && <p role="alert" className="mt-4 text-sm text-warning-copper">{auditError}</p>}
      {auditResult && repairHistory.length > 0 && <section aria-label="Persisted repair decision history" className="mt-6 border border-border-structural p-5"><h3 className="font-semibold text-off-white">Persisted repair decisions</h3><ol className="mt-3 space-y-2">{repairHistory.map((decision) => <li key={decision.id} className="text-sm text-secondary">{decision.action}{decision.proposed_replacement ? ` · ${decision.proposed_replacement}` : ""}{decision.review_reason ? ` · ${decision.review_reason}` : ""} · {new Date(decision.created_at).toLocaleString()}</li>)}</ol></section>}
    </section>
    <div className="mt-6 flex justify-between"><button type="button" onClick={() => setStep(5)} className="border border-border-structural px-5 py-3 text-sm text-off-white">Back to findings</button><button type="button" onClick={() => repairError ? setRepairReload((value) => value + 1) : goToStep(7)} disabled={repairLoading || (!repairStageComplete && !repairError)} className="bg-verification-mint px-5 py-3 text-sm font-semibold text-graphite-base disabled:opacity-40">{repairLoading ? "Checking proposals…" : repairError ? "Retry repair check" : repairStageComplete ? "Continue to Evaluation" : "Complete repair review to continue"}</button></div>
  </div></main></>;
  const stateNotice = (state: State) => state.kind === "idle" ? null : <p className={`mt-4 text-sm ${state.kind === "error" ? "text-warning-copper" : state.kind === "success" ? "text-verification-mint" : "text-secondary"}`}>{state.message}</p>;
  return <>{authPrompt}<main className="min-h-screen px-4 pb-12 pt-24 sm:px-6 lg:px-12"><div className="mx-auto max-w-6xl">
    <div className="mb-10 flex flex-wrap items-end justify-between gap-4"><div><p className="font-mono text-xs uppercase tracking-[0.2em] text-verification-mint">Interactive walkthrough</p><h1 className="mt-2 text-3xl font-semibold text-off-white sm:text-4xl">Launch Studio</h1><p className="mt-2 text-secondary">Human approval remains separate from imports and sample decisions.</p>{workspaceLoading && <p role="status" className="mt-2 text-xs text-secondary">Restoring active workspace…</p>}{workspaceId && <p className="mt-2 break-all font-mono text-xs text-secondary">Active session · {workspaceId}</p>}{restoreNotice && <p role="status" className="mt-3 max-w-2xl border border-warning-copper/40 p-3 text-sm text-warning-copper">{restoreNotice}</p>}</div><button type="button" onClick={restart} className="text-sm text-secondary underline underline-offset-4 hover:text-off-white">Start new session</button></div>
    {renderStepper()}
    <section className={step === 7 ? "hidden" : "min-h-[420px] border border-border-structural bg-surface-container-low p-6 sm:p-10"}>
      {step === 1 && <div><h2 className="text-xl font-semibold text-off-white">1. Add brand guidelines</h2><p className="mt-2 text-secondary">Upload one PDF. The API retains the original file in private server-side storage and persists document metadata plus unverified candidate rules. Upload does not approve candidates, and the original PDF is never served from a public URL.</p><label className="mt-8 block cursor-pointer border-2 border-dashed border-border-structural p-10 text-center transition hover:border-verification-mint focus-within:border-verification-mint"><span className="text-off-white">Choose a primary guideline PDF</span><span className="mt-2 block text-xs text-secondary">PDF, up to 10 MiB</span><input className="sr-only" type="file" accept="application/pdf,.pdf" onChange={uploadPdf} disabled={pdf.kind === "loading"} /></label>{pdf.kind !== "idle" && <p role={pdf.kind === "error" ? "alert" : "status"} aria-live="polite" className={`mt-4 text-sm ${pdf.kind === "error" ? "text-warning-copper" : pdf.kind === "success" ? "text-verification-mint" : "text-secondary"}`}>{pdf.message}</p>}
      {pdf.kind === "error" && <label className="mt-4 inline-block cursor-pointer border border-border-structural px-4 py-2 text-sm text-off-white hover:border-verification-mint">Try another PDF<input className="sr-only" type="file" accept="application/pdf,.pdf" onChange={uploadPdf} /></label>}
      {selectedPdf && !document && <div className="mt-6 flex items-center justify-between gap-3 border border-border-structural bg-graphite-base p-4"><span className="break-words text-sm text-off-white">Selected PDF · {selectedPdf.name}</span><button type="button" aria-label="Clear selected PDF" onClick={clearPdfSelection} disabled={pdf.kind === "loading"} className="border border-border-structural px-3 py-1 text-lg leading-none text-off-white hover:border-warning-copper disabled:opacity-50">×</button></div>}
      {document && <div className="mt-6 border border-border-structural bg-graphite-base p-5 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs uppercase tracking-wider text-verification-mint">Guideline document · persisted metadata</p><h3 className="mt-2 break-words text-lg font-semibold text-off-white">{document.filename}</h3></div><div className="flex items-center gap-3"><span className="rounded-full border border-verification-mint/40 px-3 py-1 text-xs text-verification-mint">Ingested</span><button type="button" aria-label="Clear guideline PDF" onClick={clearPdfSelection} disabled={pdf.kind === "loading"} className="border border-border-structural px-3 py-1 text-lg leading-none text-off-white hover:border-warning-copper disabled:opacity-50">×</button></div></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><div className="border border-border-structural p-4"><span className="text-xs text-secondary">File size</span><p className="mt-1 text-off-white">{(document.size_bytes / (1024 * 1024)).toFixed(2)} MiB</p></div><div className="border border-border-structural p-4"><span className="text-xs text-secondary">Pages</span><p className="mt-1 text-off-white">{document.page_count}</p></div><div className="border border-border-structural p-4"><span className="text-xs text-secondary">Candidate rules</span><p className="mt-1 text-off-white">{document.candidate_rule_count}</p></div><div className="border border-border-structural p-4"><span className="text-xs text-secondary">Extraction</span><p className="mt-1 break-words text-off-white">{document.extraction_status.replaceAll("_", " ")}</p></div></div>
      <div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={() => setPreviewOpen(!previewOpen)} disabled={!previewUrl} className="border border-border-structural px-4 py-2 text-sm text-off-white hover:border-verification-mint disabled:opacity-40">{previewOpen ? "Close PDF preview" : "Preview PDF"}</button><details className="min-w-0"><summary className="cursor-pointer border border-border-structural px-4 py-2 text-sm text-off-white hover:border-verification-mint">Document details</summary><dl className="mt-3 grid min-w-0 gap-3 border border-border-structural p-4 text-sm sm:grid-cols-2"><div><dt className="text-secondary">Persistent document ID</dt><dd className="mt-1 break-all font-mono text-xs text-off-white">{document.document_id}</dd></div><div><dt className="text-secondary">SHA-256</dt><dd className="mt-1 break-all font-mono text-xs text-off-white">{document.sha256}</dd><button type="button" className="mt-2 text-xs text-verification-mint underline" onClick={() => { void navigator.clipboard.writeText(document.sha256); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }}>{copied ? "Copied" : "Copy fingerprint"}</button></div><div><dt className="text-secondary">Ingested</dt><dd className="mt-1 text-off-white">{document.created_at ? new Date(document.created_at).toLocaleString() : "Not provided"}</dd></div><div><dt className="text-secondary">Ingestion status</dt><dd className="mt-1 break-words text-off-white">{document.extraction_status}</dd></div></dl></details></div>
      <p className="mt-3 text-xs text-secondary">PDF preview is available only from this selected file in this session. The server stores metadata and candidates, not the PDF binary.</p>{previewOpen && previewUrl && <div className="mt-4"><p className="mb-2 break-words text-sm text-secondary">Local preview · {selectedPdf?.name}</p><iframe title={`Local PDF preview: ${selectedPdf?.name}`} src={previewUrl} className="h-[65vh] min-h-96 w-full border border-border-structural bg-white" /><p className="mt-2 text-xs text-secondary">If your browser cannot show PDFs here, <a href={previewUrl} target="_blank" rel="noreferrer" className="text-verification-mint underline">open the selected PDF in a new tab</a>.</p></div>}
      <div className="mt-6 border-t border-border-structural pt-5"><div className="flex flex-wrap items-center justify-between gap-3"><h4 className="font-semibold text-off-white">Extracted candidate rules</h4>{rules && <span className="text-xs text-secondary">{rules.length} returned by API</span>}</div><p className="mt-1 text-xs text-secondary">Candidates are extracted suggestions, not approved rules.</p>{rulesLoading && <p role="status" className="mt-4 text-sm text-secondary">Loading candidate rules from the API…</p>}{rulesError && <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 text-sm text-warning-copper"><span>Candidate details could not be loaded: {rulesError}</span><button type="button" onClick={() => void loadRules(document.document_id, workspaceId!)} disabled={rulesLoading} className="border border-warning-copper/40 px-3 py-1 text-off-white disabled:opacity-50">Retry</button></div>}{rules && rules.length === 0 && <p className="mt-4 text-sm text-secondary">Ingestion succeeded, but no candidate rules were extracted from this PDF.</p>}{rules && rules.length > 0 && <ol className="mt-4 space-y-3">{rules.map((rule, index) => <li key={rule.id} className="border border-border-structural p-4 sm:p-5"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold text-off-white">Candidate {index + 1} <span className="font-mono text-xs text-secondary">· {rule.id.slice(0, 8)}</span></p><span className="rounded-full border border-warning-copper/40 px-2.5 py-1 text-xs text-warning-copper">{rule.review_status.replaceAll("_", " ")}</span></div><p className="mt-3 whitespace-pre-wrap break-words leading-relaxed text-off-white">{rule.rule_text}</p><p className="mt-3 break-words text-xs text-secondary">Source: {rule.source_filename} · page {rule.source_page}{rule.category ? ` · ${rule.category}` : ""}</p><details className="mt-2"><summary className="cursor-pointer text-xs text-secondary">Source span</summary><p className="mt-2 break-all font-mono text-xs text-secondary">Characters {rule.source_start_offset}–{rule.source_end_offset} · {rule.source_excerpt}</p></details></li>)}</ol>}</div></div>}
      </div>}
      {step === 2 && <div><h2 className="text-xl font-semibold text-off-white">2. Import facts and terminology</h2><div className="mt-4 border border-warning-copper/40 bg-warning-copper-dim p-4 text-sm text-off-white"><strong>Imported records are saved as pending review. Uploading evidence does not automatically approve it.</strong><p className="mt-2 text-secondary">After import, inspect the records and have a human reviewer approve or reject each one.</p></div><div className="mt-6 grid items-start gap-5 lg:grid-cols-2">
      {(["facts", "terms"] as const).map((kind) => { const state = kind === "facts" ? facts : terms; const title = kind === "facts" ? "Approved facts CSV" : "Terminology CSV"; const template = kind === "facts" ? "/templates/proofmint_facts_template.csv" : "/templates/proofmint_terminology_template.csv"; const sample = kind === "facts" ? "/templates/proofmint_facts_illustrative_sample.csv" : "/templates/proofmint_terminology_illustrative_sample.csv"; const required = kind === "facts" ? "approved_statement, claim_type" : "term"; const optional = kind === "facts" ? "fact_id, source_document, page_span, verified_date, status" : "preferred_form, category, usage_notes"; return <section key={kind} aria-labelledby={`${kind}-upload-title`} className="min-w-0 border border-border-structural bg-graphite-base p-5 sm:p-6"><h3 id={`${kind}-upload-title`} className="text-lg font-semibold text-off-white">{title}</h3><p className="mt-2 text-sm leading-relaxed text-secondary">{kind === "facts" ? "Factual claims about your product or company that can be checked against trustworthy supporting evidence." : "Preferred brand terms, product names, and terminology restrictions."}</p><p className="mt-3 text-xs text-secondary">Accepted format: .csv · Encoding: UTF-8 (with or without BOM)</p><div className="mt-4 text-sm"><p className="text-off-white"><strong>Required columns:</strong> <code>{required}</code></p><p className="mt-2 text-secondary">{kind === "facts" ? <><code>approved_statement</code> is the exact claim wording; <code>claim_type</code> classifies the claim. The API accepts any nonblank claim type up to 100 characters; it does not define a fixed list.</> : <><code>term</code> is the terminology entry. The API accepts any nonblank category up to 100 characters; it does not define fixed category values.</>}</p><p className="mt-2 text-secondary"><strong>Optional columns:</strong> <code>{optional}</code></p></div><div className="mt-4 border border-border-structural p-3"><p className="text-xs uppercase tracking-wider text-secondary">Illustrative example · not verified company evidence</p><code className="mt-2 block break-words text-xs text-verification-mint">{kind === "facts" ? "approved_statement,claim_type" : "term,category"}<br />{kind === "facts" ? '"Example claim to verify",product_capability' : '"Example Product",product_name'}</code></div><div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm"><a className="text-verification-mint underline underline-offset-4" href={template} download={kind === "facts" ? "proofmint_facts.csv" : "proofmint_terminology.csv"}>Download blank template</a><a className="text-secondary underline underline-offset-4 hover:text-off-white" href={sample} download>Illustrative sample CSV</a></div><label className={`mt-5 block cursor-pointer border border-dashed p-4 transition hover:border-verification-mint ${state.loading ? "pointer-events-none opacity-60" : "border-border-structural"}`}><span className="font-medium text-off-white">Choose {kind === "facts" ? "facts" : "terminology"} CSV</span><span className="mt-1 block text-xs text-secondary">.csv · UTF-8</span><input className="sr-only" type="file" accept=".csv,text/csv" disabled={state.loading} onChange={(event) => uploadCsv(kind, event)} /></label>{state.filename && <div className="mt-3 flex items-center justify-between gap-3 border border-border-structural bg-[#171A1D] p-3"><p className="min-w-0 break-words text-sm text-secondary">Selected: <span className="text-off-white">{state.filename}</span> · {(state.size / 1024).toFixed(1)} KB</p><button type="button" aria-label={kind === "facts" ? "Remove selected facts CSV" : "Remove selected terminology CSV"} onClick={() => clearCsvSelection(kind === "facts" ? "fact" : "term")} disabled={state.loading || evidenceActionId !== null} className="shrink-0 border border-border-structural px-2 py-1 text-lg leading-none text-off-white hover:border-warning-copper disabled:opacity-50">×</button></div>}{state.loading && <p role="status" className="mt-3 text-sm text-secondary">Importing {state.filename}…</p>}{state.error && <p role="alert" className="mt-3 text-sm text-warning-copper">Import failed: {state.error}</p>}{csvRemoveError[kind === "facts" ? "fact" : "term"] && <p role="alert" className="mt-3 text-sm text-warning-copper">Could not remove this import: {csvRemoveError[kind === "facts" ? "fact" : "term"]}</p>}{state.response && <div className="mt-4 border-t border-border-structural pt-4"><p className={`text-sm font-semibold ${state.response.summary.rows_rejected ? "text-warning-copper" : "text-verification-mint"}`}>{state.response.summary.rows_rejected ? "Partial import" : state.response.summary.rows_imported ? "Import complete" : (state.response.summary.rows_skipped ?? 0) ? "No new rows; duplicates skipped" : "No rows imported"}</p><p className="mt-2 text-sm text-off-white">{kind === "facts" ? "Facts" : "Terminology"}</p><p className="mt-1 text-sm text-secondary">Imported: {state.response.summary.rows_imported} · Duplicates skipped: {state.response.summary.rows_skipped ?? 0} · Rejected: {state.response.summary.rows_rejected} · Review status: <code>{"pending_review"}</code></p>{state.response.summary.rows_read === 0 && <p className="mt-2 text-sm text-secondary">The API returned no data rows.</p>}{state.response.errors.length > 0 && <div className="mt-3"><p className="text-sm font-medium text-warning-copper">Rejected row details</p><ul className="mt-2 space-y-2">{state.response.errors.map((row) => <li key={row.row_number} className="break-words border-l-2 border-warning-copper/50 pl-3 text-xs text-secondary"><strong className="text-off-white">Row {row.row_number}:</strong> {Object.entries(row.errors).map(([field, message]) => `${field}: ${message}`).join("; ")}</li>)}</ul></div>}</div>}</section>; })}</div></div>}
      {step === 2 && <section className="mt-8 border-t border-border-structural pt-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold text-off-white">Review imported evidence</h3><p className="mt-1 text-sm text-secondary">Statuses and record details are loaded from the API.</p></div><button type="button" onClick={() => void refreshImportedEvidence()} disabled={evidenceLoading} className="border border-border-structural px-3 py-2 text-sm text-off-white disabled:opacity-50">{evidenceLoading ? "Refreshing…" : "Refresh records"}</button></div>{evidenceLoading && <p role="status" className="mt-3 text-sm text-secondary">Loading imported records…</p>}{evidenceError && <p role="alert" className="mt-3 text-sm text-warning-copper">Could not load or update imported evidence: {evidenceError}</p>}{!evidenceLoading && !evidenceError && importedEvidence.length === 0 && <p className="mt-4 border border-border-structural p-4 text-sm text-secondary">No imported facts or terminology records were returned. Upload a CSV to begin review.</p>}{importedEvidence.length > 0 && <ul className="mt-4 space-y-3">{importedEvidence.map((item) => <li key={`${item.kind}-${item.id}`} className="border border-border-structural bg-graphite-base p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs uppercase tracking-wider text-verification-mint">{item.kind === "fact" ? "Imported fact" : "Imported terminology"}</p><p className="mt-2 whitespace-pre-wrap break-words font-medium text-off-white">{item.label}</p>{item.detail && <p className="mt-2 break-words text-sm text-secondary">{item.detail}</p>}<p className="mt-2 break-words text-xs text-secondary">Record ID <span className="font-mono">{item.id}</span> · {item.source_filename} · source row {item.source_row_number}</p></div><span className={`shrink-0 border px-2 py-1 text-xs ${item.review_status === "approved" ? "border-verification-mint/40 text-verification-mint" : item.review_status === "rejected" ? "border-warning-copper/40 text-warning-copper" : "border-border-structural text-secondary"}`}>{item.review_status.replaceAll("_", " ")}</span></div><div className="mt-3"><button type="button" disabled={evidenceActionId !== null} onClick={() => void removeImportBatch(item.kind, item.source_sha256)} className="border border-warning-copper/40 px-3 py-1 text-xs text-warning-copper disabled:opacity-50">{evidenceActionId === item.source_sha256 ? "Removing…" : "Remove import batch"}</button></div>{item.review_status === "pending_review" && <div className="mt-4 flex gap-3"><button type="button" disabled={evidenceActionId !== null} onClick={() => void decideImportedEvidence(item, "approve")} className="bg-verification-mint px-3 py-2 text-sm font-semibold text-graphite-base disabled:opacity-50">{evidenceActionId === item.id ? "Saving…" : "Approve"}</button><button type="button" disabled={evidenceActionId !== null} onClick={() => void decideImportedEvidence(item, "reject")} className="border border-border-structural px-3 py-2 text-sm text-off-white disabled:opacity-50">Reject</button></div>}</li>)}</ul>}</section>}
      {step === 3 && <div><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-off-white">3. Review candidate rules</h2>{rules && <span className="text-sm text-secondary">Pending {rules.filter((r) => r.review_status === "pending_review").length} · Approved {rules.filter((r) => r.review_status === "approved").length} · Rejected {rules.filter((r) => r.review_status === "rejected").length}</span>}</div><p className="mt-2 text-secondary">Approve only rules you want the local sample audit to check. Decisions are saved through the backend.</p>{!document && <div className="mt-6 border border-warning-copper/40 p-4 text-sm text-warning-copper">No uploaded document is selected. <button type="button" onClick={() => setStep(1)} className="underline">Return to Step 1</button> to upload a PDF.</div>}{document && <p className="mt-4 break-words text-sm text-secondary">Source document: <span className="text-off-white">{document.filename}</span></p>}{rulesLoading && <p role="status" className="mt-4 text-secondary">Loading candidate rules…</p>}{rulesError && <div role="alert" className="mt-4 text-warning-copper">{rulesError} <button type="button" onClick={() => document && void loadRules(document.document_id, workspaceId!)} className="ml-2 underline">Retry</button></div>}{reviewError && <p role="alert" className="mt-4 text-warning-copper">Review update failed: {reviewError}</p>}{document && rules && rules.length === 0 && <p className="mt-6 border border-border-structural p-5 text-secondary">Ingestion succeeded, but no candidate rules were extracted.</p>}{rules && rules.length > 0 && <ol className="mt-6 space-y-3">{rules.map((rule) => <li key={rule.id} className="border border-border-structural bg-graphite-base p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="font-semibold text-off-white">Candidate · <span className="break-all font-mono text-xs text-secondary">{rule.id}</span></p><p className="mt-3 whitespace-pre-wrap break-words leading-relaxed text-off-white">{rule.rule_text}</p><p className="mt-3 break-words text-xs text-secondary">{rule.source_filename} · page {rule.source_page} · characters {rule.source_start_offset}–{rule.source_end_offset}</p></div><span className={`shrink-0 border px-2 py-1 text-xs ${rule.review_status === "approved" ? "border-verification-mint/40 text-verification-mint" : rule.review_status === "rejected" ? "border-warning-copper/40 text-warning-copper" : "border-border-structural text-secondary"}`}>{rule.review_status.replaceAll("_", " ")}</span></div>{rule.review_status === "pending_review" && <div className="mt-4 flex gap-3"><button type="button" disabled={reviewingRule !== null} onClick={() => void reviewRule(rule.id, "approve")} className="bg-verification-mint px-4 py-2 text-sm font-semibold text-graphite-base disabled:opacity-50">{reviewingRule === rule.id ? "Saving…" : "Approve"}</button><button type="button" disabled={reviewingRule !== null} onClick={() => void reviewRule(rule.id, "reject")} className="border border-border-structural px-4 py-2 text-sm text-off-white disabled:opacity-50">Reject</button></div>}</li>)}</ol>}</div>}
      {step === 4 && <div><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-off-white">4. Submit marketing copy</h2><span className="rounded border border-verification-mint/40 px-2 py-1 text-xs text-verification-mint">Backend audit</span></div><p className="mt-2 text-secondary">The API stores the content hash and findings, not the full submitted copy. Evaluation uses approved rules and evidence only and is deterministic, literal, and limited.</p><section aria-label="Example marketing copy — Northstar Cloud (fictional)" className="mt-5 border border-border-structural bg-graphite-base p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-off-white">Example marketing copy — Northstar Cloud (fictional)</h3><p className="mt-1 text-xs text-secondary">Illustrative test content. Replace it with your own copy, then edit it before submitting if needed.</p></div><button type="button" onClick={() => { const selection = chooseExampleCopy(copy); if (selection.needsConfirmation) setShowExampleReplacePrompt(true); else { setCopy(selection.copy); setShowExampleReplacePrompt(false); } }} className="border border-verification-mint/50 px-3 py-2 text-sm text-verification-mint">Use example</button></div><p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-secondary">{NORTHSTAR_EXAMPLE_COPY}</p><p className="mt-3 border-t border-border-structural pt-3 text-xs text-secondary">To test preferred-term repair, import terminology with <code>term,preferred_form</code> such as <code>NorthStarCloud,Northstar Cloud</code>, then approve that imported term in Step 2. Imports start pending review, so a repair appears only after an approved mapping exists in this workspace.</p>{showExampleReplacePrompt && <div role="group" aria-label="Replace marketing copy confirmation" className="mt-3 flex flex-wrap items-center gap-3 border-t border-border-structural pt-3"><p className="text-xs text-warning-copper">This will replace the copy currently in the editor.</p><button type="button" onClick={() => { setCopy(chooseExampleCopy(copy, true).copy); setShowExampleReplacePrompt(false); }} className="bg-verification-mint px-3 py-2 text-xs font-semibold text-graphite-base">Replace with example</button><button type="button" onClick={() => setShowExampleReplacePrompt(false)} className="border border-border-structural px-3 py-2 text-xs text-off-white">Keep current copy</button></div>}</section>{auditError && <p role="alert" className="mt-4 border border-warning-copper/40 p-3 text-sm text-warning-copper">{auditError}</p>}<textarea aria-label="Marketing copy" value={copy} onChange={(event) => setCopy(event.target.value)} className="mt-6 h-48 w-full border border-border-structural bg-graphite-base p-4 text-off-white outline-none focus:border-verification-mint" placeholder="Enter the marketing copy to check against approved rules and evidence" />{auditResult && auditResult.submittedText !== copy && <p role="status" className="mt-3 text-sm text-warning-copper">The current copy differs from audit {auditResult.id.slice(0, 8)}. Run a new audit before review or clearance.</p>}<button type="button" onClick={() => void runAudit()} disabled={!copy.trim() || auditLoading} className="mt-4 bg-verification-mint px-5 py-3 font-semibold text-graphite-base disabled:opacity-40">{auditLoading ? "Running audit…" : "Run audit"}</button></div>}
      {step === 5 && <div><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold text-off-white">5. Review findings</h2><span className="rounded border border-verification-mint/40 px-2 py-1 text-xs text-verification-mint">Persisted audit</span></div>{auditRestored && <p role="status" className="mt-3 text-sm text-secondary">This persisted audit was restored for the active workspace. Submitted copy is not stored by the API.</p>}{!auditResult && <div className="mt-6 border border-border-structural p-5 text-secondary">No audit has been run. <button type="button" onClick={() => setStep(4)} className="text-verification-mint underline">Return to Step 4</button>.</div>}{auditResult && auditResult.submittedText !== copy && <div className="mt-6 border border-warning-copper/40 p-5 text-warning-copper">This audit belongs to an earlier copy. Rerun the audit before making clearance decisions. <button type="button" onClick={() => setStep(4)} className="ml-2 underline">Edit copy</button></div>}{auditResult && auditResult.submittedText === copy && <><p className="mt-3 break-all text-xs text-secondary">Audit {auditResult.id} · SHA-256 {auditResult.content_sha256} · {new Date(auditResult.created_at).toLocaleString()}</p><p className="mt-2 text-xs text-secondary">Approved rules considered: {auditResult.approved_rules_considered} · Checks performed: {auditResult.supported_checks_performed} · Rules unevaluated: {auditResult.rules_unevaluated} · Review: {auditResult.review_status}</p><div className="mt-4 border border-warning-copper/40 p-4 text-sm text-secondary"><strong className="text-warning-copper">Coverage limitations</strong><ul className="mt-2 list-disc pl-5">{auditResult.scope_limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>{auditError && <p role="alert" className="mt-4 text-sm text-warning-copper">{auditError}</p>}{auditRefreshMessage && <p role="status" className="mt-4 text-sm text-verification-mint">{auditRefreshMessage}</p>}<button type="button" onClick={() => void refreshAudit(auditResult.id)} disabled={auditRefreshing} className="mt-4 border border-border-structural px-3 py-2 text-sm text-off-white disabled:opacity-50">{auditRefreshing ? "Refreshing…" : "Refresh persisted audit"}</button>{auditResult.findings.length === 0 && <p className="mt-5 border border-border-structural p-5 text-secondary">No matching findings were returned. This does not establish compliance or publication approval.</p>}<ol className="mt-5 space-y-4">{auditResult.findings.map((finding, index) => <li key={finding.id} className="border border-border-structural p-5"><p className="text-xs uppercase tracking-wider text-warning-copper">Finding {index + 1} · {finding.finding_type} · {finding.status}</p><p className="mt-3 whitespace-pre-wrap break-words text-off-white">{auditResult.submittedText.slice(Math.max(0, finding.match_start - 50), finding.match_start)}<mark className="bg-warning-copper/30 text-off-white">{finding.matched_phrase}</mark>{auditResult.submittedText.slice(finding.match_end, Math.min(auditResult.submittedText.length, finding.match_end + 50))}</p><p className="mt-3 text-sm text-secondary">{finding.explanation}</p>{finding.suggested_correction && <p className="mt-2 text-sm text-secondary">Suggested correction: <span className="text-verification-mint">{finding.suggested_correction}</span></p>}<p className="mt-2 break-words text-xs text-secondary">{finding.source_filename || "Source filename unavailable"}{finding.source_page ? ` · page ${finding.source_page}` : ""}{finding.source_start_offset !== null ? ` · source characters ${finding.source_start_offset}–${finding.source_end_offset}` : ""}{finding.rule_id ? ` · rule ${finding.rule_id}` : ""}{finding.fact_id ? ` · fact ${finding.fact_id}` : ""}{finding.term_id ? ` · term ${finding.term_id}` : ""}</p>{finding.evidence_excerpt && <details className="mt-2"><summary className="cursor-pointer text-xs text-secondary">Evidence excerpt</summary><p className="mt-2 break-words text-sm text-secondary">{finding.evidence_excerpt}</p></details>}{finding.status === "pending_review" && <div className="mt-4 flex flex-wrap gap-3">{finding.suggested_correction && <button type="button" disabled={decisionLoading} onClick={() => void decideFinding(finding.id, "accept_suggestion")} className="bg-verification-mint px-3 py-2 text-sm text-graphite-base disabled:opacity-50">Accept suggestion</button>}<button type="button" disabled={decisionLoading} onClick={() => void decideFinding(finding.id, "flag")} className="border border-warning-copper/50 px-3 py-2 text-sm text-warning-copper disabled:opacity-50">Flag for review</button><button type="button" disabled={decisionLoading} onClick={() => void decideFinding(finding.id, "dismiss")} className="border border-border-structural px-3 py-2 text-sm text-off-white disabled:opacity-50">Dismiss</button></div>}</li>)}</ol><div className="mt-6 border-t border-border-structural pt-5"><p className="text-sm text-secondary">Clearance is an explicit human decision, not an automatic result of this audit.</p>{auditResult.clearance && <p className="mt-2 text-sm text-verification-mint">Clearance decision: {auditResult.clearance.decision} · {new Date(auditResult.clearance.created_at).toLocaleString()}</p>}<div className="mt-3 flex flex-wrap gap-3"><button type="button" disabled={clearanceLoading} onClick={() => void decideClearance("cleared")} className="bg-verification-mint px-4 py-2 text-sm font-semibold text-graphite-base disabled:opacity-50">{clearanceLoading ? "Saving…" : "Issue clearance"}</button><button type="button" disabled={clearanceLoading} onClick={() => void decideClearance("hold")} className="border border-warning-copper/50 px-4 py-2 text-sm text-warning-copper disabled:opacity-50">Place on hold</button></div></div></>}</div>}
    </section>
    {step !== 7 && <div className="mt-6 flex items-center justify-between"><button type="button" disabled={step === 1} onClick={() => setStep((current) => current - 1)} className="border border-border-structural px-5 py-3 text-sm text-off-white disabled:opacity-40">Previous</button>{step < 5 && <button type="button" onClick={() => setStep((current) => current + 1)} className="bg-off-white px-5 py-3 text-sm font-semibold text-graphite-base">Continue</button>}{step === 5 && <button type="button" onClick={() => goToStep(6)} className="bg-verification-mint px-5 py-3 text-sm font-semibold text-graphite-base">Continue to Repair</button>}{step === 6 && <button type="button" onClick={() => goToStep(7)} disabled={!repairStageComplete} className="bg-verification-mint px-5 py-3 text-sm font-semibold text-graphite-base disabled:opacity-40">Continue to Evaluation</button>}</div>}{step === 7 && (
    <div className="min-h-[420px] border border-border-structural bg-surface-container-low p-6 sm:p-10">
      <h2 className="text-xl font-semibold text-off-white">7. Evaluation &amp; Ambiguity Radar</h2>
      {auditResult && <p className="mt-3 break-all font-mono text-xs text-secondary">Persisted audit ID · {auditResult.id}</p>}
      <p className="mt-2 text-sm text-secondary">Run the labelled benchmark and review evidence-backed ambiguity signals from this workspace.</p>

      <section className="mt-6 border border-border-structural bg-graphite-base p-5">
        <h3 className="text-lg font-semibold text-off-white">Current persisted audit</h3>
        {!auditResult && <p className="mt-3 text-sm text-secondary">No persisted audit is loaded for this session.</p>}
        {auditResult && <>
          <p className="mt-2 text-xs text-secondary">Audit {auditResult.id} · created {new Date(auditResult.created_at).toLocaleString()} · {auditResult.review_status}</p>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">{[
            ["Findings", auditResult.findings.length],
            ["Pending / flagged", auditResult.findings.filter((f) => ["pending_review", "flagged"].includes(f.status)).length],
            ["Dismissed", auditResult.findings.filter((f) => f.status === "dismissed").length],
            ["Accepted", repairSummary.accepted], ["Edited", repairSummary.edited], ["Rejected", repairSummary.rejected],
            ["No supported repair", repairResult ? repairSummary.withoutEligibleRepair : "—"],
          ].map(([label, count]) => <div key={label} className="border border-border-structural p-3"><dt className="text-xs text-secondary">{label}</dt><dd className="mt-1 text-lg font-semibold text-off-white">{count}</dd></div>)}</dl>
          <p className="mt-4 text-sm text-secondary">Evidence verification · Verified {auditResult.findings.filter((f) => f.verification_status === "verified").length} · Uncertain {auditResult.findings.filter((f) => f.verification_status === "uncertain").length} · Rejected {auditResult.findings.filter((f) => f.verification_status === "rejected").length}</p>
          <p className={`mt-3 text-sm ${clearanceReadiness.canIssueClearance && auditResult.clearance?.decision === "cleared" ? "text-verification-mint" : "text-warning-copper"}`}>Clearance: {auditResult.clearance ? `${auditResult.clearance.decision} · ${new Date(auditResult.clearance.created_at).toLocaleString()}` : clearanceReadiness.canIssueClearance ? "No persisted clearance decision" : `Blocked · ${clearanceReadiness.reason}`}</p>
        </>}
      </section>

      <section className="mt-6 border border-border-structural bg-graphite-base p-5">
        <h3 className="text-lg font-semibold text-off-white">Final content review</h3>
        {!auditResult && <p className="mt-2 text-sm text-secondary">Run or open an audit to review its submitted copy and persisted decisions.</p>}
        {auditResult && <div className="mt-4 grid gap-4 lg:grid-cols-2"><div className="border border-border-structural p-4"><h4 className="text-sm font-semibold text-off-white">Original submitted copy · unchanged</h4><pre className="mt-3 whitespace-pre-wrap break-words text-sm text-secondary">{auditResult.submittedText || "Original text is not stored by the API. Restore the exact audited copy in Step 4 to preview it."}</pre></div><div className="border border-verification-mint/30 p-4"><h4 className="text-sm font-semibold text-off-white">Reviewed preview · {reviewedCopy.unavailable ? "unavailable" : `${reviewedCopy.applied} persisted decision${reviewedCopy.applied === 1 ? "" : "s"} shown`}</h4><pre className="mt-3 whitespace-pre-wrap break-words text-sm text-secondary">{reviewedCopy.content ?? "A matching server repair preview is required. No correction is applied to the original copy."}</pre></div></div>}
        {auditResult && <div className="mt-5"><h4 className="text-sm font-semibold text-off-white">Persisted repair decision history</h4>{repairHistory.length === 0 ? <p className="mt-2 text-sm text-secondary">No repair decisions have been recorded.</p> : <ol className="mt-3 space-y-2">{repairHistory.map((item) => { const finding = auditResult.findings.find((entry) => entry.id === item.finding_id); return <li key={item.id} className="border border-border-structural p-3 text-sm"><p className="text-off-white">{item.action.toUpperCase()} · {finding?.finding_type.replaceAll("_", " ") ?? "finding"} · {finding?.matched_phrase ?? item.finding_id}</p>{item.proposed_replacement && <p className="mt-1 text-verification-mint">Saved wording: {item.proposed_replacement}</p>}<p className="mt-1 text-xs text-secondary">{finding?.source_filename ?? "Evidence source unavailable"}{finding?.source_page ? ` · page ${finding.source_page}` : ""} · {new Date(item.created_at).toLocaleString()}</p></li>; })}</ol>}</div>}
      </section>

      <AmbiguityRadarPanel radar={ambiguityRadar} loading={ambiguityLoading} error={ambiguityError} onRefresh={() => void loadAmbiguityRadar()} />
      <section className="mt-8 border border-border-structural bg-graphite-base p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-semibold text-off-white">Labelled evaluation</h3><p className="mt-1 text-sm text-secondary">Runs the checked-in synthetic benchmark in an isolated in-memory database.</p></div><button type="button" onClick={() => void loadEvaluation()} disabled={evaluationLoading} className="border border-border-structural px-4 py-2 text-sm text-off-white disabled:opacity-50">{evaluationLoading ? "Running…" : "Run evaluation"}</button></div>
        {evaluationError && <p role="alert" className="mt-4 text-sm text-warning-copper">Evaluation failed: {evaluationError}</p>}
        {evaluationResult && <>
          <p className="mt-3 text-xs text-secondary">Synthetic dataset: {String(evaluationResult.dataset ?? "unknown")} · {String(evaluationResult.synthetic_cases ?? "—")} cases. These benchmark results are separate from the current persisted audit above.</p>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">{[["True positives", String(findingMetrics.true_positives ?? "—")], ["False positives", String(findingMetrics.false_positives ?? "—")], ["False negatives", String(findingMetrics.false_negatives ?? "—")], ["Precision", String(findingMetrics.precision ?? "—")], ["Recall", String(findingMetrics.recall ?? "—")], ["Evidence outcomes matched", String(evidenceMetrics.outcome_matches ?? "—")], ["Evidence mismatches", String(evidenceMetrics.outcome_mismatches ?? "—")], ["Consistent runs", `${String(consistencyMetrics.consistent_cases ?? "—")} / ${String(consistencyMetrics.cases ?? "—")}`], ["Valid repairs", `${String(repairMetrics.valid_repairs ?? "—")} / ${String(repairMetrics.repair_cases ?? "—")}`], ["Safe repair refusals", String(repairMetrics.safe_repair_refusals ?? "—")]].map(([label, value]) => <div key={String(label)} className="border border-border-structural p-3"><dt className="text-xs text-secondary">{label}</dt><dd className="mt-1 text-lg font-semibold text-off-white">{value}</dd></div>)}</dl>
          <p className="mt-4 text-sm text-secondary">Evidence observed: verified {String(observedEvidence.verified ?? "—")}, uncertain {String(observedEvidence.uncertain ?? "—")}, rejected {String(observedEvidence.rejected ?? "—")} · Expected: verified {String(expectedEvidence.verified ?? "—")}, uncertain {String(expectedEvidence.uncertain ?? "—")}, rejected {String(expectedEvidence.rejected ?? "—")}</p>
          <details className="mt-4 border border-border-structural p-3"><summary className="cursor-pointer text-sm text-verification-mint">Evaluation raw details</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs text-secondary">{JSON.stringify(evaluationResult, null, 2)}</pre></details>
        </>}
      </section>

      <div className="mt-6 flex items-center justify-between"><button type="button" onClick={() => setStep(6)} className="border border-border-structural px-5 py-3 text-sm text-off-white">Previous</button><Link href="/" className="inline-flex items-center gap-2 bg-verification-mint px-5 py-3 text-sm font-semibold text-graphite-base"><Check aria-hidden="true" size={16} />Finish</Link></div>
    </div>
  )
  }
  </div></main></>;
}
