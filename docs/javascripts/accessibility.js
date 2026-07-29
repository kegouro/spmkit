function enhanceAccessibility(root = document) {
  root.querySelectorAll(".md-typeset__scrollwrap").forEach((region, index) => {
    if (!region.hasAttribute("tabindex")) {
      region.setAttribute("tabindex", "0");
    }
    if (!region.hasAttribute("role")) {
      region.setAttribute("role", "region");
    }
    if (!region.hasAttribute("aria-label")) {
      region.setAttribute("aria-label", `Scrollable table ${index + 1}`);
    }
  });

  const search = root.querySelector(".md-search[role='dialog']");
  if (search && !search.hasAttribute("aria-label")) {
    search.setAttribute("aria-label", "Site search");
  }

  root.querySelectorAll(".md-code__nav").forEach((navigation, index) => {
    navigation.setAttribute("aria-label", `Code actions ${index + 1}`);
  });

  root.querySelectorAll("nav.md-nav").forEach((navigation, index) => {
    const labelledBy = navigation.getAttribute("aria-labelledby");
    const label = labelledBy
      ? root.getElementById(labelledBy)?.textContent?.trim()
      : "Documentation";
    navigation.setAttribute("aria-label", `${label || "Documentation"} section ${index + 1}`);
    navigation.removeAttribute("aria-labelledby");
  });
}

document.addEventListener("DOMContentLoaded", () => enhanceAccessibility());

if (typeof document$ !== "undefined") {
  document$.subscribe(() => enhanceAccessibility());
}
