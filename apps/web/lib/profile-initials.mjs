export function getProfileInitials(firstName, surname) {
  const first = typeof firstName === "string" ? firstName.trim().split(/\s+/)[0] : "";
  const last = typeof surname === "string" ? surname.trim().split(/\s+/)[0] : "";
  return `${first.slice(0, 1)}${last.slice(0, 1)}`.toLocaleUpperCase() || "U";
}
