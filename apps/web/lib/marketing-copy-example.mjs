export const NORTHSTAR_EXAMPLE_COPY = "NorthStarCloud helps workspace administrators export reports to CSV. Our revolutionary reporting tools help teams review operational data. NorthStarCloud provides reliable access to workspace reporting.";

/** @param {string} currentCopy @param {boolean} confirmed */
export function chooseExampleCopy(currentCopy, confirmed = false) {
  if (currentCopy.trim() && currentCopy !== NORTHSTAR_EXAMPLE_COPY && !confirmed) {
    return { copy: currentCopy, needsConfirmation: true };
  }
  return { copy: NORTHSTAR_EXAMPLE_COPY, needsConfirmation: false };
}
