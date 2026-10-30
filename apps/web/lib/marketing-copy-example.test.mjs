import assert from "node:assert/strict";
import test from "node:test";

import { chooseExampleCopy, NORTHSTAR_EXAMPLE_COPY } from "./marketing-copy-example.mjs";

test("Use example returns the configured content for an empty editor", () => {
  assert.deepEqual(chooseExampleCopy(""), { copy: NORTHSTAR_EXAMPLE_COPY, needsConfirmation: false });
  assert.match(NORTHSTAR_EXAMPLE_COPY, /NorthStarCloud helps workspace administrators export reports to CSV/);
  assert.match(NORTHSTAR_EXAMPLE_COPY, /revolutionary reporting tools/);
});

test("example selection does not silently overwrite user copy", () => {
  assert.deepEqual(chooseExampleCopy("My draft"), { copy: "My draft", needsConfirmation: true });
  assert.deepEqual(chooseExampleCopy("My draft", true), { copy: NORTHSTAR_EXAMPLE_COPY, needsConfirmation: false });
});

test("example remains available to ordinary editing after selection", () => {
  const selected = chooseExampleCopy("").copy;
  const edited = `${selected} Edited by the user.`;
  assert.notEqual(edited, selected);
  assert.equal(chooseExampleCopy(edited).copy, edited);
});
