import assert from "node:assert/strict";
import test from "node:test";
import { getProfileInitials } from "./profile-initials.mjs";

test("profile avatar initials use the actual first and surname", () => {
  assert.equal(getProfileInitials("Keshav", "Modi"), "KM");
  assert.equal(getProfileInitials("Akshara", "Jain"), "AJ");
  assert.equal(getProfileInitials("Yuvraj", "Rathore"), "YR");
});

test("profile avatar initials tolerate whitespace and missing names", () => {
  assert.equal(getProfileInitials("  Ada Lovelace ", "  Byron King"), "AB");
  assert.equal(getProfileInitials("Grace", ""), "G");
  assert.equal(getProfileInitials("", ""), "U");
});
