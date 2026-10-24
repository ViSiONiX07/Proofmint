import assert from "node:assert/strict";
import test from "node:test";

import {
  ACTIVE_WORKSPACE_STORAGE_KEY,
  clearActiveWorkspace,
  readActiveWorkspace,
  saveActiveWorkspace,
} from "./workspace-session.mjs";

function createSessionStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

test("active workspace survives a page reload within the same tab", () => {
  const tabSessionStorage = createSessionStorage();
  saveActiveWorkspace(tabSessionStorage, "workspace-a");

  // A new page instance reading the same tab's sessionStorage sees the same ID.
  assert.equal(readActiveWorkspace(tabSessionStorage), "workspace-a");
});

test("starting a new session removes only the active workspace pointer", () => {
  const tabSessionStorage = createSessionStorage();
  saveActiveWorkspace(tabSessionStorage, "workspace-a");

  clearActiveWorkspace(tabSessionStorage);

  assert.equal(readActiveWorkspace(tabSessionStorage), null);
  assert.equal(ACTIVE_WORKSPACE_STORAGE_KEY, "proofmint.activeWorkspaceId");
});

test("blank workspace pointers are not restored", () => {
  const tabSessionStorage = createSessionStorage();
  saveActiveWorkspace(tabSessionStorage, "   ");

  assert.equal(readActiveWorkspace(tabSessionStorage), null);
});
