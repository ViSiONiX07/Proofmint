export const ACTIVE_WORKSPACE_STORAGE_KEY = "proofmint.activeWorkspaceId";

/** @param {Pick<Storage, "getItem">} storage */
export function readActiveWorkspace(storage) {
  const workspaceId = storage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY);
  return workspaceId && workspaceId.trim() ? workspaceId : null;
}

/** @param {Pick<Storage, "setItem">} storage @param {string} workspaceId */
export function saveActiveWorkspace(storage, workspaceId) {
  storage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspaceId);
}

/** @param {Pick<Storage, "removeItem">} storage */
export function clearActiveWorkspace(storage) {
  storage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
}
