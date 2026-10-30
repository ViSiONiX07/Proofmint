import assert from "node:assert/strict";
import test from "node:test";

import {
  describeAppliedRevision,
  describeExtractionComparison,
  parseExtractionRevision,
  parseExtractionRevisionPreview,
  summarizeExtractionPreview,
} from "./extraction-revision.mjs";

const WORKSPACE_ID = "6f1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6071";
const DOCUMENT_ID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const REVISION_ID = "9a8b7c6d-5e4f-4a3b-2c1d-0e1f2a3b4c5d";
const SHA = "a".repeat(64);

const unchanged = {
  comparison: "unchanged",
  source_page: 1,
  source_start_offset: 0,
  source_end_offset: 40,
  existing_rule_id: "11111111-1111-4111-8111-111111111111",
  existing_rule_text: 'Never use the exact phrase "guaranteed" in copy.',
  existing_review_status: "approved",
  extracted_rule_text: 'Never use the exact phrase "guaranteed" in copy.',
  extracted_category: "prohibition",
  decision_carried_forward: true,
};

const added = {
  comparison: "added",
  source_page: 1,
  source_start_offset: 120,
  source_end_offset: 190,
  existing_rule_id: null,
  existing_rule_text: null,
  existing_review_status: null,
  extracted_rule_text: "Imported candidate rules must remain pending review until a human approves them.",
  extracted_category: "prohibition",
  decision_carried_forward: false,
};

const removed = {
  comparison: "removed",
  source_page: 2,
  source_start_offset: 10,
  source_end_offset: 90,
  existing_rule_id: "22222222-2222-4222-8222-222222222222",
  existing_rule_text: "Human review and clearance\nImported candidate rules must remain",
  existing_review_status: "approved",
  extracted_rule_text: null,
  extracted_category: null,
  decision_carried_forward: false,
};

const preview = {
  workspace_id: WORKSPACE_ID,
  document_id: DOCUMENT_ID,
  source_filename: "Northstar.pdf",
  source_sha256: SHA,
  page_count: 2,
  current_revision: 1,
  next_revision: 2,
  already_current: false,
  existing_rule_count: 2,
  extracted_rule_count: 2,
  unchanged_count: 1,
  changed_count: 0,
  added_count: 1,
  removed_count: 1,
  comparisons: [unchanged, removed, added],
  limitations: ["Refresh re-runs the deterministic extractor against the retained original PDF."],
};

const revision = {
  workspace_id: WORKSPACE_ID,
  document_id: REVISION_ID,
  supersedes_document_id: DOCUMENT_ID,
  extraction_revision: 2,
  already_existed: false,
  source_filename: "Northstar.pdf",
  source_sha256: SHA,
  page_count: 2,
  file_size_bytes: 4096,
  candidate_rule_count: 2,
  approved_rule_count: 1,
  pending_rule_count: 1,
  rejected_rule_count: 0,
  carried_forward_decisions: 1,
  removed_rule_count: 1,
  created_at: "2026-10-27T09:00:00Z",
  limitations: ["A candidate whose source page, character span, and text are unchanged keeps the existing human decision."],
};

test("a well-formed preview is accepted and bound to its document and workspace", () => {
  const parsed = parseExtractionRevisionPreview(preview, { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID });
  assert.ok(parsed);
  assert.equal(parsed.comparisons.length, 3);
  // The same payload is refused when the caller is looking at another document or workspace.
  assert.equal(parseExtractionRevisionPreview(preview, { documentId: REVISION_ID, workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevisionPreview(preview, { documentId: DOCUMENT_ID, workspaceId: REVISION_ID }), null);
  assert.equal(parseExtractionRevisionPreview(null, { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
});

test("a comparison that claims a side it cannot have is refused rather than shown", () => {
  const withExisting = { ...added, existing_rule_id: unchanged.existing_rule_id };
  const withExtracted = { ...removed, extracted_rule_text: "invented wording" };
  const commented = { ...added, existing_review_status: "approved" };
  for (const item of [withExisting, withExtracted, commented]) {
    assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [item] },
      { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  }
  const emptySpan = { ...unchanged, source_end_offset: unchanged.source_start_offset };
  assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [emptySpan] },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  const zeroPage = { ...unchanged, source_page: 0 };
  assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [zeroPage] },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
});

test("a decision is carried forward only onto an identical, already-reviewed rule", () => {
  const unreviewed = { ...unchanged, existing_review_status: "pending_review" };
  assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [unreviewed] },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  // A reworded span changes the rule text, so no decision may ride along with it.
  const reworded = { ...unchanged, comparison: "changed", decision_carried_forward: true };
  assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [reworded] },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  const honestRewrite = parseExtractionRevisionPreview({
    ...preview, unchanged_count: 0, changed_count: 1,
    comparisons: [{ ...reworded, decision_carried_forward: false }, removed, added],
  }, { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID });
  assert.ok(honestRewrite);
  assert.equal(honestRewrite.comparisons[0].decision_carried_forward, false);
});

test("counts that disagree with the comparison list, or a duplicate span, are refused", () => {
  assert.equal(parseExtractionRevisionPreview({ ...preview, removed_count: 0 },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevisionPreview({ ...preview, changed_count: 1 },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevisionPreview({ ...preview, comparisons: [...preview.comparisons, removed] },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevisionPreview({ ...preview, next_revision: 5 },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevisionPreview({ ...preview, source_sha256: "not-a-hash" },
    { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }), null);
});

test("the summary separates what changes from what is preserved", () => {
  const parsed = parseExtractionRevisionPreview(preview, { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID });
  const summary = summarizeExtractionPreview(parsed);
  assert.deepEqual(summary.counts, { unchanged: 1, changed: 0, added: 1, removed: 1 });
  assert.equal(summary.totalSpans, 3);
  assert.equal(summary.changingSpans, 2);
  assert.equal(summary.newPending, 1);
  assert.equal(summary.carriedDecisions, 1);
  assert.equal(summary.revisionLabel, "Rule-set revision 1 → 2");
  assert.match(summary.headline, /2 of 3 source spans would change/);
  assert.match(summary.reviewNotice, /1 refreshed candidate would start as pending review/);
  assert.match(summary.removalNotice, /1 malformed or superseded rule would be omitted/);
});

test("an already-current preview promises no change instead of a diff", () => {
  const current = {
    ...preview,
    already_current: true,
    existing_rule_count: 2,
    extracted_rule_count: 2,
    unchanged_count: 2,
    changed_count: 0,
    added_count: 0,
    removed_count: 0,
    comparisons: [unchanged, { ...unchanged, source_start_offset: 41, source_end_offset: 80, existing_rule_id: "33333333-3333-4333-8333-333333333333", existing_review_status: "rejected" }],
  };
  const summary = summarizeExtractionPreview(parseExtractionRevisionPreview(current, { documentId: DOCUMENT_ID, workspaceId: WORKSPACE_ID }));
  assert.equal(summary.changingSpans, 0);
  assert.equal(summary.newPending, 0);
  assert.equal(summary.carriedDecisions, 2);
  assert.match(summary.headline, /already match the corrected extractor/);
  assert.equal(summary.reviewNotice, "No refreshed candidate would start unreviewed.");
  assert.equal(summary.removalNotice, "No stored rule would be omitted.");
});

test("each comparison is labeled with its source page and character span", () => {
  const labeled = describeExtractionComparison(removed, "Northstar.pdf");
  assert.equal(labeled.comparisonLabel, "Omitted from the new revision");
  assert.equal(labeled.spanLabel, "page 2 · characters 10–90");
  assert.equal(labeled.sourceLabel, "Northstar.pdf · page 2");
  assert.equal(labeled.existingText, removed.existing_rule_text);
  assert.equal(labeled.extractedText, null);
  assert.match(labeled.decisionLabel, /keeps this rule and its human decision/);
  const pending = describeExtractionComparison(added, "Northstar.pdf");
  assert.equal(pending.existingStatusLabel, null);
  assert.match(pending.decisionLabel, /Starts as pending review/);
});

test("applied revisions must account for every candidate and name what they supersede", () => {
  const parsed = parseExtractionRevision(revision, { workspaceId: WORKSPACE_ID });
  assert.ok(parsed);
  assert.equal(parseExtractionRevision(revision, { workspaceId: DOCUMENT_ID }), null);
  // A fresh revision that supersedes nothing is refused.
  assert.equal(parseExtractionRevision({ ...revision, supersedes_document_id: null }, { workspaceId: WORKSPACE_ID }), null);
  // Candidate counts must add up, and carried decisions cannot exceed reviewed rules.
  assert.equal(parseExtractionRevision({ ...revision, approved_rule_count: 5 }, { workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevision({ ...revision, carried_forward_decisions: 2, approved_rule_count: 0, rejected_rule_count: 0, pending_rule_count: 2 }, { workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevision({ ...revision, source_sha256: "short" }, { workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevision({ ...revision, file_size_bytes: 0 }, { workspaceId: WORKSPACE_ID }), null);
  assert.equal(parseExtractionRevision({ ...revision, created_at: "not a date" }, { workspaceId: WORKSPACE_ID }), null);
});

test("an applied revision reports preserved provenance without claiming approvals", () => {
  const applied = describeAppliedRevision(parseExtractionRevision(revision, { workspaceId: WORKSPACE_ID }));
  assert.equal(applied.documentId, REVISION_ID);
  assert.equal(applied.headline, "Rule-set revision 2 created with 2 extracted candidates.");
  assert.equal(applied.detailLabel, "1 pending review · 1 approved · 0 rejected");
  assert.match(applied.carriedLabel, /1 identical rule kept an existing human decision; the rest need review/);
  assert.match(applied.removalLabel, /the superseded revision keeps them/);

  const replay = describeAppliedRevision(parseExtractionRevision({
    ...revision, already_existed: true, document_id: DOCUMENT_ID, extraction_revision: 1,
    supersedes_document_id: null, candidate_rule_count: 4, approved_rule_count: 1, pending_rule_count: 1,
    rejected_rule_count: 2, carried_forward_decisions: 0, removed_rule_count: 0,
  }, { workspaceId: WORKSPACE_ID }));
  assert.equal(replay.headline, "No new revision was needed. Rule-set revision 1 already matches the corrected extractor.");
  assert.equal(replay.carriedLabel, "Nothing was written and no stored rule changed.");
  assert.equal(replay.removalLabel, "Every stored rule of the superseded revision is still recorded there.");
});
