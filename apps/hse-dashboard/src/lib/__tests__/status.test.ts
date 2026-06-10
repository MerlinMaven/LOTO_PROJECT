import { describe, expect, it } from "vitest";
import {
  ALL_STATUSES,
  STATUS_CLASSES,
  STATUS_LABELS,
  STATUS_SHORT,
  allowedTransitions,
  canTransition,
  isEditable,
} from "../status";
import type { ProcedureStatus } from "@/types/procedure";

// ── Completeness ──────────────────────────────────────────────────────────────

describe("ALL_STATUSES", () => {
  it("contains exactly the four lifecycle statuses", () => {
    expect(ALL_STATUSES).toHaveLength(4);
    expect(ALL_STATUSES).toContain("draft_pending_review");
    expect(ALL_STATUSES).toContain("approved");
    expect(ALL_STATUSES).toContain("published");
    expect(ALL_STATUSES).toContain("archived");
  });
});

describe("STATUS_LABELS / STATUS_SHORT / STATUS_CLASSES", () => {
  it("have an entry for every status", () => {
    for (const s of ALL_STATUSES) {
      expect(STATUS_LABELS[s]).toBeTruthy();
      expect(STATUS_SHORT[s]).toBeTruthy();
      expect(STATUS_CLASSES[s]).toBeTruthy();
    }
  });
});

// ── canTransition ─────────────────────────────────────────────────────────────

describe("canTransition", () => {
  const VALID: [ProcedureStatus, ProcedureStatus][] = [
    ["draft_pending_review", "approved"],
    ["approved", "published"],
    ["published", "archived"],
  ];

  it.each(VALID)("%s → %s is valid", (from, to) => {
    expect(canTransition(from, to)).toBe(true);
  });

  it("draft_pending_review → published is invalid (skip step)", () => {
    expect(canTransition("draft_pending_review", "published")).toBe(false);
  });

  it("approved → draft_pending_review is invalid (backwards)", () => {
    expect(canTransition("approved", "draft_pending_review")).toBe(false);
  });

  it("archived → published is invalid (terminal state)", () => {
    expect(canTransition("archived", "published")).toBe(false);
  });

  it("archived has no valid transitions", () => {
    expect(allowedTransitions("archived")).toHaveLength(0);
  });
});

// ── allowedTransitions ────────────────────────────────────────────────────────

describe("allowedTransitions", () => {
  it("returns [approved] for draft_pending_review", () => {
    expect(allowedTransitions("draft_pending_review")).toEqual(["approved"]);
  });

  it("returns [published] for approved", () => {
    expect(allowedTransitions("approved")).toEqual(["published"]);
  });

  it("returns [archived] for published", () => {
    expect(allowedTransitions("published")).toEqual(["archived"]);
  });

  it("returns [] for archived", () => {
    expect(allowedTransitions("archived")).toEqual([]);
  });
});

// ── isEditable ────────────────────────────────────────────────────────────────

describe("isEditable", () => {
  it("returns true only for draft_pending_review", () => {
    expect(isEditable("draft_pending_review")).toBe(true);
  });

  it("returns false for approved", () => {
    expect(isEditable("approved")).toBe(false);
  });

  it("returns false for published", () => {
    expect(isEditable("published")).toBe(false);
  });

  it("returns false for archived", () => {
    expect(isEditable("archived")).toBe(false);
  });
});
