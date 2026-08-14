import assert from "node:assert/strict";
import test from "node:test";

import { navHrefForEvidenceMode, navItemForPath, sidebarFor } from "./sidebar-config";

test("navigation exposes distinct live and rehearsal entry points", () => {
  const poweruserItems = sidebarFor("poweruser").flatMap((section) => section.items);
  assert.equal(poweruserItems.some((item) => item.href === "/admin/acquisition/"), true);
  assert.equal(poweruserItems.some((item) => item.href === "/rehearsal/"), true);
  assert.equal(navItemForPath("/rehearsal/", "poweruser")?.label, "Rehearsal landing");
});

test("mission links move into the rehearsal namespace only after selection", () => {
  assert.equal(navHrefForEvidenceMode("/dashboard/", "live"), "/dashboard/");
  assert.equal(navHrefForEvidenceMode("/dashboard/", "rehearsal"), "/rehearsal/dashboard/");
  assert.equal(navItemForPath("/rehearsal/dashboard/", "poweruser")?.label, "Unified decision workspace");
});

test("rehearsal landing remains visible to every authenticated role", () => {
  for (const role of ["poweruser", "viewer"] as const) {
    const items = sidebarFor(role).flatMap((section) => section.items);
    assert.equal(items.some((item) => item.href === "/rehearsal/"), true, role);
  }
});
